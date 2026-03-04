# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import json
import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select
from pathlib import Path
from apps.common.postgres import postgres
from apps.llm import LLM, embedding, token_calculator
from apps.models import MCPTools
from apps.models.task import ExecutorHistory
from apps.schemas.llm import LLMFunctions, LLMToolCall
from apps.schemas.task import AgentHistoryExtra, TaskData

from .base import MCPBase
from .context import ContextConfig, ContextManager
from ...schemas.mcp import MCPServerInfo
from ...services.mcp_service import MCPServiceManager

_logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
config = ContextConfig(
    short_window_size=5,  # 滑动窗口：保留最近 N 轮对话
    ctx_length=128000,  # 模型最大上下文长度
    token_safety_ratio=0.8,  # Token 安全占比
    enable_abstract_replace=True,  # 开启摘要替换
    enable_stopword_filter=True,  # 开启停用词过滤
    enable_smart_truncation=True,  # 开启兜底截断
    stop_words_path=Path.cwd() / "apps" / "common" / "stopwords.txt",
)
NO_INTERMEDIATE_STREAM_TOOLS = {"self_introduce", "update_todo_list", "read_todo_list"}


class MCPHost(MCPBase):
    """MCP宿主服务"""

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

    def _collect_tool_calls(self, context: list[ExecutorHistory], start_index: int) -> list[dict[str, Any]]:
        """收集从 start_index 开始的所有连续 tool 消息，构建 tool_calls 列表"""
        tool_calls = []
        j = start_index + 1

        while j < len(context):
            next_ctx = context[j]
            next_extra = self._parse_extra_data(next_ctx)

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

    def _build_assistant_message_from_ctx(
            self,
            ctx: ExecutorHistory,
            context: list[ExecutorHistory],
            current_index: int,
    ) -> dict[str, Any] | None:
        """从 context 构建 assistant 消息（包含 tool_calls）"""
        assistant_content = ctx.inputData.get("assistant", "")
        # 收集后续的 tool_calls
        tool_calls = self._collect_tool_calls(context, current_index)

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

    def build_messages(
            self,
            task: TaskData,
            system_prompt: str,
    ) -> list[dict[str, Any]]:
        """构建LLM消息列表"""
        # 首先添加系统提示词
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        system_prompt_token_length = token_calculator.calculate_token_length(messages)
        _logger.info("[MCPHost] 系统提示词(Token长度: %d)", system_prompt_token_length)

        # 遍历历史记录，构建消息
        msg_index = 0
        while msg_index < len(task.context):
            ctx = task.context[msg_index]
            extra = self._parse_extra_data(ctx)

            if not extra or not extra.role:
                msg_index += 1
                continue

            # 根据 role 构建对应消息
            msg = None
            if extra.role == "user":
                msg = {"role": "user", "content": ctx.inputData.get("user", "")}
            elif extra.role == "assistant":
                msg = self._build_assistant_message_from_ctx(ctx, task.context, msg_index)
            elif extra.role == "tool" and extra.tool_call_id:
                msg = self._build_tool_message_from_ctx(ctx, extra.tool_call_id)

            if msg:
                messages.append(msg)

            msg_index += 1
        return messages

    async def call_llm_and_parse_tools(
            self,
            task: TaskData,
            llm: LLM,
            tool_list: dict[str, MCPTools],
            system_prompt: str,
    ) -> tuple[str, list[LLMToolCall] | None]:
        """调用LLM并解析工具调用"""
        # 构建消息
        messages = self.build_messages(task, system_prompt)
        _logger.info("[MCPHost] LLM最大上下文窗口大小: %d，LLM总上下文长度: %d", llm.config.maxToken,
                     llm.config.ctxLength)

        messages = self.build_messages(task, system_prompt)
        before_token_length = token_calculator.calculate_token_length(messages)
        _logger.info("[MCPHost] 构建消息完成，Token长度: %d，消息数量: %d", before_token_length, len(messages))

        # 获取当前llm上下文长度
        config.ctx_length = llm.config.ctxLength

        fixed_messages = await ContextManager.build(messages=messages, conversation_id=task.metadata.conversationId,
                                                    config=config)  # noqa: E501
        after_token_length = token_calculator.calculate_token_length(fixed_messages)
        _logger.info("[MCPHost] 消息修正完成，Token长度: %d，消息数量: %d", after_token_length, len(fixed_messages))

        # 创建工具列表
        llm_tools = [
            LLMFunctions(
                name=tool.toolName,
                description=tool.description,
                param_schema=tool.inputSchema,
            )
            for tool in tool_list.values()
        ]

        # 非流式调用LLM，获取thinking和tool_call
        full_response = None
        async for chunk in llm.call(messages, streaming=False, tools=llm_tools, include_thinking=True, temperature=0):
            full_response = chunk

        if not full_response:
            err = "[MCPHost] LLM未返回有效响应"
            _logger.error(err)
            raise RuntimeError(err)

        # 保存大模型回复的文字内容
        text_response = ""
        if full_response.reasoning_content:
            text_response += full_response.reasoning_content
        if full_response.content:
            if text_response:
                text_response += "\n"
            text_response += full_response.content
        if text_response:
            _logger.info("[MCPHost] LLM思考过程: %s", text_response)

        return text_response, full_response.tool_call

    async def select_tools(
            self,
            query: str,
            mcp_list: list[str] | None = None,
            top_n: int = 15,
    ) -> dict[str, MCPTools]:
        """使用 Embedding 选择最贴近 query 的 top N 工具"""
        # 检查 embedding 是否已初始化
        if embedding.MCPToolVector is None:
            _logger.warning("[MCPHost] Embedding 未初始化，返回空字典")
            return {}

        query_embedding = await embedding.get_embedding([query])
        async with postgres.session() as session:
            stmt = select(embedding.MCPToolVector)

            # 如果提供了 mcp_list，则过滤
            if mcp_list:
                stmt = stmt.where(embedding.MCPToolVector.mcpId.in_(mcp_list))

            # 按余弦距离排序并限制返回数量
            stmt = stmt.order_by(
                embedding.MCPToolVector.embedding.cosine_distance(query_embedding[0]),
            ).limit(top_n)

            tool_vecs = await session.scalars(stmt)
            tool_ids = [tool_vec.id for tool_vec in tool_vecs]

        # 根据工具 ID 获取完整的工具信息
        if not tool_ids:
            _logger.info("[MCPHost] 未找到匹配的工具")
            return {}

        async with postgres.session() as session:
            result = await session.scalars(
                select(MCPTools).where(MCPTools.id.in_(tool_ids)),
            )
            tools = {tool.toolName: tool for tool in result.all()}

        _logger.info("[MCPHost] 为查询 '%s' 选择了 %d 个工具", query, len(tools))
        return tools

    async def get_tools(
            self,
            mcp_list: list[str] | None = None,
            user_id: str = "root",
    ) -> dict[str, MCPTools]:
        """
        通过 get_mcp_tools 方法获取 MCPTools 信息（取消 Embedding 向量匹配）
        :param mcp_list: 要过滤的 MCP ID 列表，None 则返回所有 MCP 的工具
        :return: 以 toolName 为 key、MCPTools 实例为 value 的字典
        """  # noqa: D205
        all_tools: list[MCPTools] = []

        target_mcp_ids: list[str] = mcp_list or []
        if not target_mcp_ids:
            mcp_servers: list[MCPServerInfo] = await MCPServiceManager.get_mcp_servers(user_id=user_id)
            target_mcp_ids = [mcp.mcp_id for mcp in mcp_servers]
        _logger.warning("[MCPHost] 获取工具 | 输入 MCP 列表: %s | 处理后目标 MCP 列表: %s", mcp_list, target_mcp_ids)

        for mcp_id in target_mcp_ids:
            # 过滤无效的 MCP ID（空字符串/非字符串）
            if not isinstance(mcp_id, str) or not mcp_id:
                _logger.warning("[MCPHost] 无效的 MCP ID：%s，跳过", mcp_id)
                continue

            try:
                # 调用 get_mcp_tools 方法
                mcp_tools = await MCPServiceManager.get_mcp_tools(
                    mcp_id=mcp_id,  # 去除首尾空格，避免无效 ID
                    user_id=user_id,
                )
                # 检查返回值类型
                if isinstance(mcp_tools, list):
                    all_tools.extend(mcp_tools)
                else:
                    _logger.warning("[MCPHost] MCP %s 的工具列表格式异常：%s", mcp_id, type(mcp_tools))
                    continue

            except Exception as e:  # noqa: BLE001
                _logger.warning("[MCPHost] 获取 MCP %s 的工具失败：%s", mcp_id, str(e))
                continue

        # 构建工具字典（自动去重：相同 toolName 保留最后一个）
        return {tool.toolName: tool for tool in all_tools}
