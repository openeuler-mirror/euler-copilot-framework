# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""工作流中步骤相关函数"""

import inspect
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
import json

from pydantic import ConfigDict

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.empty import Empty
from apps.scheduler.call.facts.facts import FactsCall
from apps.scheduler.call.reply.direct_reply import DirectReply
from apps.scheduler.call.slot.schema import SlotOutput
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.call.summary.summary import Summary
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.step_config import should_use_direct_conversation_format
from apps.scheduler.pool.pool import Pool
from apps.scheduler.variable.integration import VariableIntegration
from apps.schemas.enum_var import (
    EventType,
    SpecialCallType,
    StepStatus
)
from apps.schemas.message import TextAddContent
from apps.schemas.scheduler import CallError, CallOutputChunk
from apps.schemas.task import FlowStepHistory, StepQueueItem
from apps.services.node import NodeManager

logger = logging.getLogger(__name__)


class StepExecutor(BaseExecutor):
    """工作流中步骤相关函数"""

    step: StepQueueItem

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def __init__(self, **kwargs: Any) -> None:
        """初始化"""
        super().__init__(**kwargs)
        self.validate_flow_state(self.task)

    @staticmethod
    async def check_cls(call_cls: Any) -> bool:
        """检查Call是否符合标准要求"""
        flag = True
        if not hasattr(call_cls, "_init") or not callable(call_cls._init):  # noqa: SLF001
            flag = False
        if not hasattr(call_cls, "_exec") or not inspect.isasyncgenfunction(call_cls._exec):  # noqa: SLF001
            flag = False
        if not hasattr(call_cls, "info") or not callable(call_cls.info):
            flag = False
        return flag

    @staticmethod
    async def get_call_cls(call_id: str) -> type[CoreCall]:
        """获取并验证Call类"""
        # 特判，用于处理隐藏节点
        if call_id == SpecialCallType.EMPTY.value:
            return Empty
        if call_id == SpecialCallType.SUMMARY.value:
            return Summary
        if call_id == SpecialCallType.FACTS.value:
            return FactsCall
        if call_id == SpecialCallType.SLOT.value:
            return Slot
        if call_id == SpecialCallType.DIRECT_REPLY.value:
            return DirectReply
        if call_id == SpecialCallType.START.value:
            return Empty  # start节点使用Empty类
        if call_id == SpecialCallType.END.value:
            return Empty  # end节点使用Empty类

        # 从Pool中获取对应的Call
        call_cls: type[CoreCall] = await Pool().get_call(call_id)

        # 检查Call合法性
        if not await StepExecutor.check_cls(call_cls):
            err = f"[FlowExecutor] 工具 {call_id} 不符合Call标准要求"
            raise ValueError(err)

        return call_cls

    async def init(self) -> None:
        """初始化步骤"""
        logger.info("[StepExecutor] 初始化步骤 %s", self.step.step.name)

        # State写入ID和运行状态
        self.task.state.step_id = self.step.step_id  # type: ignore[arg-type]
        # type: ignore[arg-type]
        self.task.state.step_name = self.step.step.name

        # 获取并验证Call类
        node_id = self.step.step.node
        # 获取node详情并存储
        try:
            self.node = await NodeManager.get_node(node_id)
        except ValueError:
            logger.info("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self.node = None

        if self.node:
            call_cls = await StepExecutor.get_call_cls(self.node.call_id)
            self._call_id = self.node.call_id
        else:
            # 可能是特殊的内置Node
            call_cls = await StepExecutor.get_call_cls(node_id)
            self._call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self.node.known_params if self.node and self.node.known_params else {}
        )
        if self.step.step.params:
            params.update(self.step.step.params)

        # 对于需要扁平化处理的Call类型，将input_parameters中的内容提取到顶级
        # TODO Call中自带属性区分是否需要扁平化，避免逻辑判断频繁修改，或者修改Code逻辑为统一设计
        if self._call_id not in ["Code"] and "input_parameters" in params:
            # 提取input_parameters中的所有字段到顶级
            input_params = params.get("input_parameters", {})
            if isinstance(input_params, dict):
                # 将input_parameters中的字段提取到顶级
                for key, value in input_params.items():
                    params[key] = value
                # 移除input_parameters，避免重复
                params.pop("input_parameters", None)

        # 对于LLM调用，注入enable_thinking参数
        if self._call_id == "LLM" and hasattr(self.background, 'enable_thinking'):
            params['enable_thinking'] = self.background.enable_thinking

        try:
            self.obj = await call_cls.instance(self, self.node, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise

    async def _run_slot_filling(self) -> None:
        """运行自动参数填充；相当于特殊Step，但是不存库"""
        # 判断是否需要进行自动参数填充
        if not self.obj.enable_filling:
            return

        # 暂存旧数据
        current_step_id = self.task.state.step_id  # type: ignore[arg-type]
        current_step_name = self.task.state.step_name  # type: ignore[arg-type]

        # 更新State
        self.task.state.step_id = str(uuid.uuid4())  # type: ignore[arg-type]
        self.task.state.step_name = "自动参数填充"  # type: ignore[arg-type]
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.RUNNING
        self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2)

        # 初始化填参
        slot_obj = await Slot.instance(
            self,
            self.node,
            data=self.obj.input,
            current_schema=self.obj.input_model.model_json_schema(
                override=self.node.override_input if self.node and self.node.override_input else {},
            ),
        )
        # 推送填参消息
        await self.push_message(EventType.STEP_INPUT.value, slot_obj.input)
        # 运行填参
        iterator = slot_obj.exec(self, slot_obj.input)
        async for chunk in iterator:
            result: SlotOutput = SlotOutput.model_validate(chunk.content)
        self.task.tokens.input_tokens += slot_obj.tokens.input_tokens
        self.task.tokens.output_tokens += slot_obj.tokens.output_tokens

        # 如果没有填全，则状态设置为待填参
        if result.remaining_schema:
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.PARAM
        else:
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.SUCCESS
        await self.push_message(EventType.STEP_OUTPUT.value, result.model_dump(by_alias=True, exclude_none=True))

        # 更新输入
        self.obj.input.update(result.slot_data)

        # 恢复State
        self.task.state.step_id = current_step_id  # type: ignore[arg-type]
        self.task.state.step_name = current_step_name  # type: ignore[arg-type]
        self.task.tokens.input_tokens += self.obj.tokens.input_tokens
        self.task.tokens.output_tokens += self.obj.tokens.output_tokens

    async def _process_chunk(
        self,
        iterator: AsyncGenerator[CallOutputChunk, None],
        *,
        to_user: bool = False,
    ) -> str | dict[str, Any]:
        """处理Chunk"""
        content: str | dict[str, Any] = ""

        async for chunk in iterator:
            if not isinstance(chunk, CallOutputChunk):
                err = "[StepExecutor] 返回结果类型错误"
                logger.error(err)
                raise TypeError(err)
            if isinstance(chunk.content, str):
                if not isinstance(content, str):
                    content = ""
                content += chunk.content
            else:
                if not isinstance(content, dict):
                    content = {}
                content = chunk.content
            if to_user:
                if isinstance(chunk.content, str):
                    await self.push_message(EventType.TEXT_ADD.value, chunk.content)
                    self.task.runtime.answer += chunk.content
                else:
                    # 🔑 修复：非字符串内容应该通过step.output事件发送，而不是使用step.type
                    await self.push_message(EventType.STEP_OUTPUT.value, chunk.content)

        return content

    async def _save_output_parameters_to_variables(self, output_data: str | dict[str, Any]) -> None:
        """保存输出参数到变量池，并进行类型验证"""
        try:
            # 获取当前步骤的output_parameters配置
            output_parameters = None
            if self.step.step.params and isinstance(self.step.step.params, dict):
                output_parameters = self.step.step.params.get(
                    "output_parameters", {})

            if not output_parameters or not isinstance(output_parameters, dict):
                logger.debug(
                    f"[StepExecutor] 步骤 {self.step.step_id} 没有配置output_parameters")
                return

            # 解析输出数据
            if isinstance(output_data, str):
                try:
                    data_dict = json.loads(output_data)
                except json.JSONDecodeError:
                    logger.warning(
                        f"[StepExecutor] 无法解析输出数据为JSON: {output_data}")
                    data_dict = {"raw_output": output_data}
            else:
                data_dict = output_data

            # 构造变量名前缀
            var_prefix = f"{self.step.step_id}."

            # 保存每个output_parameter到变量池，并进行类型验证
            saved_count = 0
            failed_params = []

            # 特殊处理：如果是旧格式的JSON Schema结构（主要是Loop节点）
            if (isinstance(output_parameters, dict) and
                "type" in output_parameters and
                "items" in output_parameters and
                    isinstance(output_parameters["items"], dict)):

                # 提取items中的真正参数配置
                output_parameters = output_parameters["items"]

                # 清理每个参数配置中的多余字段（如嵌套的items）
                for param_name, param_config in output_parameters.items():
                    if isinstance(param_config, dict) and "items" in param_config:
                        # 移除多余的items字段，保持参数配置的简洁性
                        param_config.pop("items", None)

                logger.debug(
                    f"[StepExecutor] 转换后的output_parameters: {output_parameters}")

            for param_name, param_config in output_parameters.items():
                try:
                    # 检查param_config格式，确保它是字典
                    if not isinstance(param_config, dict):
                        logger.warning(
                            f"[StepExecutor] 输出参数 {param_name} 的配置不是字典格式: {param_config} (类型: {type(param_config)})")
                        # 如果不是字典，尝试转换为标准格式
                        if isinstance(param_config, str):
                            param_config = {
                                "type": param_config, "description": ""}
                        else:
                            param_config = {
                                "type": "string", "description": "", "raw_config": str(param_config)}

                    # 获取参数值
                    param_value = self._extract_value_from_output_data(
                        param_name, data_dict, param_config)

                    if param_value is not None:
                        # 获取期望的类型
                        raw_expected_type = param_config.get("type", "string")

                        # 映射类型到变量系统支持的类型
                        type_mapping = {
                            "integer": "number",  # integer 映射到 number
                            "int": "number",      # int 映射到 number
                            "float": "number",    # float 映射到 number
                            "str": "string",      # str 映射到 string
                            "bool": "boolean",    # bool 映射到 boolean
                            "dict": "object",     # dict 映射到 object
                        }
                        expected_type = type_mapping.get(
                            raw_expected_type, raw_expected_type)
                        if expected_type.lower() == "anyof":
                            # 处理 anyOf 类型，暂时取第一个类型作为期望类型
                            expected_type_list = param_config.get(
                                "type_list", [])
                            for i, et in enumerate(expected_type_list):
                                if et in type_mapping:
                                    expected_type_list[i] = type_mapping[et]
                        else:
                            expected_type_list = [expected_type]
                        value_validated = False
                        for et in expected_type_list:
                            if self._validate_output_value_type(param_value, et):
                                expected_type = et
                                value_validated = True
                                break
                        # 进行类型验证
                        if not value_validated:
                            error_msg = (f"输出参数 '{param_name}' 类型不匹配。"
                                         f"期望: {expected_type}, "
                                         f"实际: {type(param_value).__name__}({param_value})")
                            logger.error(f"[StepExecutor] {error_msg}")
                            failed_params.append(f"{param_name}: {error_msg}")
                            continue

                        # 构造变量名
                        var_name = f"{var_prefix}{param_name}"

                        # 保存到对话变量池
                        success = await VariableIntegration.save_conversation_variable(
                            var_name=var_name,
                            value=param_value,
                            var_type=expected_type,
                            description=param_config.get("description", ""),
                            user_sub=self.task.ids.user_sub,
                            # type: ignore[arg-type]
                            flow_id=self.task.state.flow_id,
                            conversation_id=self.task.ids.conversation_id
                        )

                        if success:
                            saved_count += 1
                            logger.debug(
                                f"[StepExecutor] 已保存输出参数变量: conversation.{var_name} = {param_value}")
                        else:
                            error_msg = f"保存输出参数变量失败: {var_name}"
                            logger.warning(f"[StepExecutor] {error_msg}")
                            failed_params.append(f"{param_name}: {error_msg}")

                except Exception as e:
                    error_msg = f"处理输出参数失败: {str(e)}"
                    logger.warning(
                        f"[StepExecutor] 保存输出参数 {param_name} 失败: {e}")
                    failed_params.append(f"{param_name}: {error_msg}")

            # 如果有失败的参数，将步骤状态设置为失败
            if failed_params:

                # type: ignore[assignment]
                self.task.state.step_status = StepStatus.ERROR

                failure_msg = f"输出参数类型验证失败:\n" + "\n".join(failed_params)
                logger.error(
                    f"[StepExecutor] 步骤 {self.step.step_id} 执行失败: {failure_msg}")

                # 保存错误信息到任务状态
                if not hasattr(self.task.state, 'error_info') or self.task.state.error_info is None:
                    self.task.state.error_info = {}
                # type: ignore[assignment]
                self.task.state.error_info['output_validation_errors'] = failed_params

                # 抛出异常以停止工作流执行
                raise ValueError(f"步骤输出参数类型验证失败: {failure_msg}")

            if saved_count > 0:
                logger.info(f"[StepExecutor] 已保存 {saved_count} 个输出参数到变量池")

        except Exception as e:
            # 如果是我们主动抛出的验证错误，重新抛出
            if "类型验证失败" in str(e):
                raise
            logger.error(f"[StepExecutor] 保存输出参数到变量池失败: {e}")
            # 对于其他意外错误，也将步骤设置为失败
            # type: ignore[assignment]
            self.task.state.step_status = StepStatus.ERROR
            raise

    def _extract_value_from_output_data(self, param_name: str, output_data: dict[str, Any], param_config: dict) -> Any:
        """从输出数据中提取参数值"""
        # 支持多种提取方式

        # 1. 直接从输出数据中获取同名key
        if param_name in output_data:
            return output_data[param_name]

        # 2. 支持路径提取（例如：result.data.value）
        if "path" in param_config:
            path = param_config["path"]
            current_data = output_data
            for key in path.split("."):
                if isinstance(current_data, dict) and key in current_data:
                    current_data = current_data[key]
                else:
                    return None
            return current_data

        # 3. 支持默认值
        if "default" in param_config:
            return param_config["default"]

        # 4. 如果参数配置为"full_output"，返回完整输出
        if param_config.get("source") == "full_output":
            return output_data

        return None

    def _validate_output_value_type(self, value: Any, expected_type: str) -> bool:
        """验证输出值的类型是否符合期望"""
        try:
            if expected_type == "string":
                return isinstance(value, str)
            elif expected_type == "number":
                return isinstance(value, (int, float))
            elif expected_type == "boolean":
                return isinstance(value, bool)
            elif expected_type == "array":
                return isinstance(value, list)
            elif expected_type == "object":
                return isinstance(value, dict)
            elif expected_type == "any":
                return True  # 任何类型都匹配
            else:
                # 对于未知类型，默认接受字符串
                logger.warning(
                    f"[StepExecutor] 未知的期望类型: {expected_type}，默认验证为字符串")
                return isinstance(value, str)
        except Exception:
            return False

    async def run(self) -> None:
        """运行单个步骤"""
        self.validate_flow_state(self.task)

        # 进行自动参数填充
        await self._run_slot_filling()

        # 更新状态
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.RUNNING
        self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2)
        # 推送输入
        await self.push_message(EventType.STEP_INPUT.value, self.obj.input)

        # 执行步骤
        iterator = self.obj.exec(self, self.obj.input,
                                 language=self.task.language)

        try:
            content = await self._process_chunk(iterator, to_user=self.obj.to_user)
        except Exception as e:
            logger.exception("[StepExecutor] 运行步骤失败，进行异常处理步骤")
            # type: ignore[arg-type]
            self.task.state.step_status = StepStatus.ERROR

            # 构建错误输出数据
            if isinstance(e, CallError):
                error_output = {
                    "error": e.message,
                    "message": e.message,
                    "data": e.data,
                }
                self.task.state.error_info = {  # type: ignore[arg-type]
                    "err_msg": e.message,
                    "data": e.data,
                }
            else:
                error_output = {
                    "error": str(e),
                    "message": str(e),
                    "data": {},
                }
                self.task.state.error_info = {  # type: ignore[arg-type]
                    "err_msg": str(e),
                    "data": {},
                }

            # 发送包含错误信息的输出
            await self.push_message(EventType.STEP_OUTPUT.value, error_output)
            return

        # 更新执行状态
        # type: ignore[arg-type]
        self.task.state.step_status = StepStatus.SUCCESS
        self.task.tokens.input_tokens += self.obj.tokens.input_tokens
        self.task.tokens.output_tokens += self.obj.tokens.output_tokens
        self.task.tokens.full_time += round(datetime.now(
            UTC).timestamp(), 2) - self.task.tokens.time

        # 更新history
        if isinstance(content, str):
            # 处理空字符串的情况，避免TextAddContent验证失败
            if not content:
                content = " "  # 使用一个空格作为占位符
            output_data = TextAddContent(text=content).model_dump(
                exclude_none=True, by_alias=True)
        else:
            output_data = content

        # 保存output_parameters到变量池
        await self._save_output_parameters_to_variables(output_data)

        # 更新context
        history = FlowStepHistory(
            task_id=self.task.id,
            flow_id=self.task.state.flow_id,  # type: ignore[arg-type]
            flow_name=self.task.state.flow_name,  # type: ignore[arg-type]
            flow_status=self.task.state.flow_status,  # type: ignore[arg-type]
            step_id=self.step.step_id,
            step_name=self.step.step.name,
            step_description=self.step.step.description,
            step_status=self.task.state.step_status,  # type: ignore[arg-type]
            input_data=self.obj.input,
            output_data=output_data,
        )
        self.task.context.append(history)

        try:
            await self.push_message(EventType.STEP_OUTPUT.value, output_data)
        except Exception as e:
            logger.error(
                f"[StepExecutor] {self.step.step.name} - push_message调用失败: {e}")
            raise
