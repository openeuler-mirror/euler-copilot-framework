# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.  # noqa: D100
import json
import logging
import uuid
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm import LLM
from apps.models.task import ExecutorHistory, LanguageType
from apps.scheduler.call.abstract.prompt import ABSTRACT_PROMPT
from apps.scheduler.call.abstract.schema import AbstractOutput
from apps.schemas.task import AgentHistoryExtra

_logger = logging.getLogger(__name__)


class AbstractGenerator:  # noqa: D101
    """摘要生成器"""
    @staticmethod
    async def generate(  # noqa: D102
            executor_history: list[ExecutorHistory],
            record_id: uuid.UUID,
            llm: LLM,
            language: LanguageType) -> AbstractOutput:

        # 2. 分步调用：加载prompt模板 + 加载执行历史
        current_prompt_tpl = AbstractGenerator._load_prompt(language)
        executor_history_messages = AbstractGenerator._load_executor_history(executor_history)

        # 3. 构建完整prompt（UUID转字符串）
        prompt = AbstractGenerator._build_prompt(record_id, current_prompt_tpl, executor_history_messages)

        # 4. 构造LLM调用的messages格式
        llm_messages = [{"role": "user", "content": prompt}]
        full_content = ""

        # 5. 调用LLM（非流式），收集返回内容
        async for llm_chunk in llm.call(
                messages=llm_messages,
                streaming=False,
                include_thinking=False,
                tools=None,
                temperature=0.7,
        ):
            # 过滤空内容，拼接有效文本
            if llm_chunk.content and llm_chunk.content.strip():
                full_content += llm_chunk.content.strip()

        # 6. 返回AbstractOutput模型（而非直接返回字符串）
        return AbstractOutput(abstract=full_content)

    @staticmethod
    def _load_prompt(language: LanguageType) -> str:
        """加载提示词模板"""
        prompt = ABSTRACT_PROMPT.copy()
        # 2. 加载当前语言对应的prompt模板并返回
        return prompt[language]

    @staticmethod
    def _collect_tool_calls(context: list[ExecutorHistory], start_index: int) -> list[dict[str, Any]]:
        """收集从 start_index 开始的所有连续 tool 消息，构建 tool_calls 列表"""
        tool_calls = []
        j = start_index + 1

        while j < len(context):
            next_ctx = context[j]
            next_extra = AbstractGenerator._parse_extra_data(next_ctx)

            # 如果不是 tool 消息，停止扫描
            if not next_extra or next_extra.role != "tool":
                break

            # 构建 tool_call
            if next_extra.tool_call_id and next_ctx.stepName:
                tool_calls.append({
                    "id": next_extra.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": next_ctx.stepName,
                        "arguments": json.dumps(next_ctx.inputData, ensure_ascii=False),
                    },
                })

            j += 1
        return tool_calls

    @staticmethod
    def _parse_extra_data(ctx: ExecutorHistory) -> AgentHistoryExtra | None:
        """解析 extraData"""
        if not ctx.extraData:
            return None
        try:
            return AgentHistoryExtra.model_validate(ctx.extraData)
        except Exception:
            _logger.exception("[MCPHost] 解析上下文extraData失败")
            return None

    @staticmethod
    def _build_assistant_message_from_ctx(
            ctx: ExecutorHistory,
            context: list[ExecutorHistory],
            current_index: int,
    ) -> dict[str, Any] | None:
        """从 context 构建 assistant 消息（包含 tool_calls）"""
        assistant_content = ctx.inputData.get("assistant", "")
        # 收集后续的 tool_calls
        tool_calls = AbstractGenerator._collect_tool_calls(context, current_index)

        # 构建 assistant 消息
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_content,
        }
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls

        return assistant_msg

    @staticmethod
    def _build_tool_message_from_ctx(ctx: ExecutorHistory, tool_call_id: str) -> dict[str, Any] | None:
        """从 context 构建 tool 消息"""
        if not ctx.outputData:
            return None
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": ctx.stepName,
            "content": json.dumps(ctx.outputData, ensure_ascii=False),
        }

    @staticmethod
    def _load_executor_history(executor_history: list[ExecutorHistory]) -> list[dict[str, Any]]:
        """
        参考MCPHost的build_messages逻辑，加载并结构化执行历史
        1. 完全复用框架成熟的extraData解析/tool_calls收集逻辑
        2. 生成LLM标准的messages列表（system/user/assistant/tool）
        3. 提取Record ID，保证和框架逻辑一致
        :param executor_history: 原始执行历史列表（来自current_history_for_abstract）
        :return: 结构化的执行历史消息列表
        """  # noqa: D205
        # 初始化LLM消息列表（先清空，避免残留）
        executor_history_messages = []

        # 遍历执行历史，构建结构化消息（完全参考MCPHost的build_messages逻辑）
        msg_index = 0
        while msg_index < len(executor_history):
            ctx = executor_history[msg_index]
            extra = AbstractGenerator._parse_extra_data(ctx)

            # 无extraData或无role则跳过（框架容错逻辑）
            if not extra or not extra.role:
                msg_index += 1
                continue

            # 根据extra.role构建对应消息（和MCPHost逻辑完全对齐）
            msg = None
            if extra.role == "user":
                user_content = ctx.inputData.get("user", "") if hasattr(ctx, "inputData") and ctx.inputData else ""
                msg = {"role": "user", "content": user_content.strip()}
            elif extra.role == "assistant":
                msg = AbstractGenerator._build_assistant_message_from_ctx(ctx, executor_history, msg_index)
            elif extra.role == "tool" and extra.tool_call_id:
                msg = AbstractGenerator._build_tool_message_from_ctx(ctx, extra.tool_call_id)
            if msg:
                executor_history_messages.append(msg)
            msg_index += 1
        return executor_history_messages

    @staticmethod
    def _build_prompt(
            record_id: uuid.UUID,
            current_prompt_tpl: str,
            executor_history_messages: list[dict[str, Any]]) -> str:
        """
        核心方法：渲染提示词模板，生成LLM可直接输入的完整prompt
        1. 初始化Jinja2沙箱环境（框架标准，避免安全风险）
        2. 将结构化消息/Record ID注入模板，渲染生成最终prompt
        :return: 完整的LLM输入prompt字符串
        """  # noqa: D205
        # 初始化Jinja2沙箱环境（框架标准写法，避免模板注入风险）
        jinja_env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=True,  # 自动转义HTML，避免XSS
            trim_blocks=True,  # 去除块标签后的换行
            lstrip_blocks=True,  # 去除块标签前的空格
        )

        # 加载模板并渲染（注入record_id和history变量）
        template = jinja_env.from_string(current_prompt_tpl)
        return template.render(
            record_id=record_id,  # 注入Record ID
            history=executor_history_messages,  # 注入结构化的执行历史
        ).strip()
