# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
Core Call类是定义了所有Call都应具有的方法和参数的PyDantic类。

所有Call类必须继承此类，并根据需求重载方法。
"""

import logging
import re
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.variable.integration import VariableIntegration
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.pool import NodePool
from apps.schemas.parameters import ValueType
from apps.schemas.scheduler import (
    CallError,
    CallIds,
    CallInfo,
    CallOutputChunk,
    CallTokens,
    CallVars,
)
from apps.schemas.task import FlowStepHistory

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor
    from apps.scheduler.call.choice.schema import Value


logger = logging.getLogger(__name__)


class DataBase(BaseModel):
    """所有Call的输入基类"""

    @classmethod
    def model_json_schema(cls, override: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """通过override参数，动态填充Schema内容"""
        schema = super().model_json_schema(**kwargs)
        if override:
            for key, value in override.items():
                schema["properties"][key] = value
        return schema


class CoreCall(BaseModel):
    """所有Call的父类，包含通用的逻辑"""

    name: SkipJsonSchema[str] = Field(description="Step的名称", exclude=True)
    description: SkipJsonSchema[str] = Field(
        description="Step的描述", exclude=True)
    node: SkipJsonSchema[NodePool | None] = Field(
        description="节点信息", exclude=True)
    enable_filling: SkipJsonSchema[bool] = Field(
        description="是否需要进行自动参数填充", default=False, exclude=True
    )
    tokens: SkipJsonSchema[CallTokens] = Field(
        description="Call的输入输出Tokens信息",
        default=CallTokens(),
        exclude=True,
    )
    input_model: ClassVar[SkipJsonSchema[type[DataBase]]] = Field(
        description="Call的输入Pydantic类型；不包含override的模板",
        exclude=True,
        frozen=True,
    )
    output_model: ClassVar[SkipJsonSchema[type[DataBase]]] = Field(
        description="Call的输出Pydantic类型；不包含override的模板",
        exclude=True,
        frozen=True,
    )
    to_user: bool = Field(description="是否需要将输出返回给用户", default=False)
    enable_variable_resolution: bool = Field(
        description="是否启用自动变量解析", default=True)
    controlled_output: bool = Field(description="是否允许用户定义输出参数", default=False)
    i18n_info: ClassVar[SkipJsonSchema[dict[str, dict]]] = {}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        lang_info = cls.i18n_info.get(
            language, cls.i18n_info[LanguageType.CHINESE])
        return CallInfo(name=lang_info["name"], type=lang_info["type"], description=lang_info["description"])

    def __init_subclass__(
        cls, input_model: type[DataBase], output_model: type[DataBase], **kwargs: Any
    ) -> None:
        """初始化子类"""
        super().__init_subclass__(**kwargs)
        cls.input_model = input_model
        cls.output_model = output_model

    @staticmethod
    def _assemble_call_vars(executor: "StepExecutor") -> CallVars:
        """组装CallVars"""
        if not executor.task.state:
            err = "[CoreCall] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        history = {}
        history_order = []
        for item in executor.task.context:
            item_obj = FlowStepHistory.model_validate(item)
            history[item_obj.step_id] = item_obj
            history_order.append(item_obj.step_id)

        return CallVars(
            ids=CallIds(
                task_id=executor.task.id,
                flow_id=executor.task.state.flow_id,
                session_id=executor.task.ids.session_id,
                conversation_id=executor.task.ids.conversation_id,
                user_sub=executor.task.ids.user_sub,
                app_id=executor.task.state.app_id,
            ),
            question=executor.question,
            history=history,
            history_order=history_order,
            summary=executor.task.runtime.summary,
        )

    @staticmethod
    def _extract_history_variables(path: str, history: dict[str, FlowStepHistory]) -> Any:
        """
        提取History中的变量

        :param path: 路径，格式为：step_id/key/to/variable
        :param history: Step历史，即call_vars.history
        :return: 变量
        """
        split_path = path.split("/")
        if len(split_path) < 1:
            err = f"[CoreCall] 路径格式错误: {path}"
            logger.error(err)
            return None
        if split_path[0] not in history:
            err = f"[CoreCall] 步骤{split_path[0]}不存在"
            logger.error(err)
            return None
        data = history[split_path[0]].output_data
        for key in split_path[2:]:
            if key not in data:
                err = f"[CoreCall] 输出Key {key} 不存在"
                logger.error(err)
                return None
            data = data[key]
        return data

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化Call类"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            **kwargs,
        )

        await obj._set_input(executor)
        return obj

    async def _initialize_variable_context(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化变量解析上下文并初始化系统变量"""
        context = {
            "question": call_vars.question,
            "user_sub": call_vars.ids.user_sub,
            "flow_id": call_vars.ids.flow_id,
            "session_id": call_vars.ids.session_id,
            "app_id": call_vars.ids.app_id,
            "conversation_id": call_vars.ids.conversation_id,
        }

        await VariableIntegration.initialize_system_variables(context)
        return context

    async def _resolve_variables_in_config(self, config: Any, call_vars: CallVars) -> Any:
        """解析配置中的变量引用

        Args:
            config: 配置值，可能包含变量引用
            call_vars: Call变量

        Returns:
            解析后的配置值
        """
        if isinstance(config, dict):
            if "reference" in config:
                # 解析变量引用
                resolved_value, _ = await VariableIntegration.resolve_variable_reference(
                    config["reference"],
                    user_sub=call_vars.ids.user_sub,
                    flow_id=call_vars.ids.flow_id,
                    conversation_id=call_vars.ids.conversation_id
                )
                return resolved_value
            elif "value" in config:
                # 使用默认值
                return config["value"]
            else:
                # 递归解析字典中的所有值
                resolved_dict = {}
                for key, value in config.items():
                    resolved_dict[key] = await self._resolve_variables_in_config(value, call_vars)
                return resolved_dict
        elif isinstance(config, list):
            # 递归解析列表中的所有值
            resolved_list = []
            for item in config:
                resolved_item = await self._resolve_variables_in_config(item, call_vars)
                resolved_list.append(resolved_item)
            return resolved_list
        elif isinstance(config, str):
            # 解析字符串中的变量引用
            return await self._resolve_variables_in_text(config, call_vars)
        else:
            # 直接返回配置值
            return config

    async def _resolve_variables_in_text(self, text: str, call_vars: CallVars) -> str:
        """解析文本中的变量引用（{{...}} 语法）

        Args:
            text: 包含变量引用的文本
            call_vars: Call变量

        Returns:
            解析后的文本
        """
        if not isinstance(text, str):
            return text

        # 检查是否包含变量引用语法
        if not re.search(r'\{\{.*?\}\}', text):
            return text

        # 提取所有变量引用并逐一解析替换
        variable_pattern = r'\{\{(.*?)\}\}'
        matches = re.findall(variable_pattern, text)

        resolved_text = text
        for match in matches:
            try:
                # 解析变量引用
                resolved_value, _ = await VariableIntegration.resolve_variable_reference(
                    match.strip(),
                    user_sub=call_vars.ids.user_sub,
                    flow_id=call_vars.ids.flow_id,
                    conversation_id=call_vars.ids.conversation_id,
                    current_step_id=getattr(self, '_step_id', None)
                )
                # 替换原始文本中的变量引用
                resolved_text = resolved_text.replace(
                    f'{{{{{match}}}}}', str(resolved_value))
            except Exception as e:
                logger.warning(f"[CoreCall] 解析变量引用 '{match}' 失败: {e}")
                # 如果解析失败，保留原始的变量引用
                continue

        return resolved_text

    async def _resolve_single_value(self, value, call_vars: CallVars):
        """解析单个变量引用

        Args:
            value: Value对象，包含type和value字段
            call_vars: Call变量上下文

        Returns:
            Value: 解析后的Value对象，如果是引用类型则解析为具体值和类型
        """
        # 🔑 将导入语句放在方法开头，避免作用域问题
        from apps.schemas.parameters import ValueType
        from apps.scheduler.variable.type import VariableType as VarType
        from apps.scheduler.call.choice.schema import Value

        # 如果不是引用类型，直接返回
        if value.type != ValueType.REFERENCE:
            return value

        try:
            # 解析变量引用
            resolved_value, resolved_type = await VariableIntegration.resolve_variable_reference(
                reference=value.value,
                user_sub=call_vars.ids.user_sub,
                flow_id=call_vars.ids.flow_id,
                conversation_id=call_vars.ids.conversation_id,
                current_step_id=getattr(self, '_step_id', None)
            )

            # 🔑 关键修复：将VariableType转换为ValueType
            # VariableType到ValueType的映射
            type_mapping = {
                VarType.STRING: ValueType.STRING,
                VarType.NUMBER: ValueType.NUMBER,
                VarType.BOOLEAN: ValueType.BOOL,
                VarType.OBJECT: ValueType.DICT,
                VarType.ARRAY_STRING: ValueType.LIST,
                VarType.ARRAY_NUMBER: ValueType.LIST,
                VarType.ARRAY_OBJECT: ValueType.LIST,
                VarType.ARRAY_ANY: ValueType.LIST,
                VarType.ARRAY_FILE: ValueType.LIST,
                VarType.ARRAY_BOOLEAN: ValueType.LIST,
                VarType.ARRAY_SECRET: ValueType.LIST,
            }

            # 转换类型
            if resolved_type in type_mapping:
                converted_type = type_mapping[resolved_type]
            else:
                # 如果没有映射，默认为STRING
                converted_type = ValueType.STRING

        except Exception as e:
            logger.warning(f"[CoreCall] 解析变量引用 '{value.value}' 失败: {e}")
            return value

        return Value(value=resolved_value, type=converted_type)

    async def _set_input(self, executor: "StepExecutor") -> None:
        """获取Call的输入"""
        self._sys_vars = self._assemble_call_vars(executor)
        self._step_id = executor.step.step_id  # 存储 step_id 用于变量名构造

        # 如果启用了变量解析，初始化变量上下文
        if self.enable_variable_resolution:
            await self._initialize_variable_context(self._sys_vars)

        input_data = await self._init(self._sys_vars)
        self.input = input_data.model_dump(by_alias=True, exclude_none=True)

    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化Call类，并返回Call的输入"""
        err = "[CoreCall] 初始化方法必须手动实现"
        raise NotImplementedError(err)

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的流式输出方法"""
        yield CallOutputChunk(type=CallOutputType.TEXT, content="")

    async def _after_exec(self, input_data: dict[str, Any]) -> None:
        """Call类实例的执行后方法"""

    async def exec(
        self,
        executor: "StepExecutor",
        input_data: dict[str, Any],
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的执行方法"""
        self._last_output_data = {}  # 初始化输出数据存储

        async for chunk in self._exec(input_data):
            # 捕获最后的输出数据
            if chunk.type == CallOutputType.DATA and isinstance(chunk.content, dict):
                self._last_output_data = chunk.content
            yield chunk

        await self._after_exec(input_data)

    async def _llm(self, messages: list[dict[str, Any]]) -> str:
        """Call可直接使用的LLM非流式调用"""
        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens
        return result

    async def _json(self, messages: list[dict[str, Any]], schema: type[BaseModel]) -> BaseModel:
        """Call可直接使用的JSON生成"""
        json = FunctionLLM()
        result = await json.call(messages=messages, schema=schema.model_json_schema())
        return schema.model_validate(result)
