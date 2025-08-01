# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型或使用程序做出判断"""

import ast
import copy
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.choice.schema import (
    Condition,
    ChoiceBranch,
    ChoiceInput,
    ChoiceOutput,
    Logic,
    Value,
)
from apps.schemas.parameters import ValueType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType, CallType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class Choice(CoreCall, input_model=ChoiceInput, output_model=ChoiceOutput):
    """Choice工具"""

    to_user: bool = Field(default=False)
    choices: list[ChoiceBranch] = Field(description="分支", default=[ChoiceBranch(),
                                        ChoiceBranch(conditions=[Condition()], is_default=False)])

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(
            name="条件分支", 
            type=CallType.LOGIC,
            description="使用大模型或使用程序做出条件判断，决定后续分支"
        )

    def _validate_branch_logic(self, choice: ChoiceBranch) -> bool:
        """验证分支的逻辑运算符是否有效
        
        Args:
            choice: 需要验证的分支
            
        Returns:
            bool: 逻辑运算符是否有效
        """
        if choice.logic not in [Logic.AND, Logic.OR]:
            logger.warning(f"[Choice] 分支 {choice.branch_id} 条件处理失败: 无效的逻辑运算符: {choice.logic}")
            return False
        return True

    async def _process_condition_value(self, value: Value, call_vars: CallVars, 
                                       branch_id: str, value_position: str) -> tuple[bool, Value, str]:
        """处理条件值（左值或右值）
        
        Args:
            value: 需要处理的值对象
            call_vars: Call变量
            branch_id: 分支ID，用于日志记录
            value_position: 值的位置描述（"左值"或"右值"）
            
        Returns:
            tuple[bool, Value, str]: (是否成功, 处理后的Value对象，错误消息)
        """
        # 处理reference类型
        if value.type == ValueType.REFERENCE:
            try:
                resolved_value = await self._resolve_single_value(value, call_vars)
            except Exception as e:
                return False, None, f"{value_position}引用解析失败: {e}"
        else:
            resolved_value = value
            
        # 对于非引用类型，先进行类型转换，然后验证值类型
        try:
            resolved_value = self._convert_value_to_expected_type(resolved_value)
        except Exception as e:
            return False, None, f"{value_position}类型转换失败: {e}"
            
        if not ConditionHandler.check_value_type(resolved_value):
            return False, None, f"{value_position}类型不匹配: {resolved_value.value} 应为 {resolved_value.type}"
            
        return True, resolved_value, ""

    def _convert_value_to_expected_type(self, value: Value) -> Value:
        """根据期望的类型转换值
        
        Args:
            value: 需要转换的Value对象
            
        Returns:
            Value: 转换后的Value对象
            
        Raises:
            ValueError: 当值无法转换为指定类型时
        """
        if value.value is None:
            return value
            
        # 如果已经是正确的类型，直接返回
        if ConditionHandler.check_value_type(value):
            return value
        
        # 创建新的Value对象进行转换
        converted_value = Value(type=value.type, value=value.value)
        
        try:
            if value.type == ValueType.NUMBER:
                # 转换为数字
                if isinstance(value.value, str):
                    if value.value.strip() == "":
                        converted_value.value = 0
                    elif '.' in value.value or 'e' in value.value.lower():
                        converted_value.value = float(value.value)
                    else:
                        converted_value.value = int(value.value)
                elif isinstance(value.value, bool):
                    converted_value.value = int(value.value)
                elif isinstance(value.value, (int, float)):
                    converted_value.value = value.value
                else:
                    converted_value.value = float(value.value)
                    
            elif value.type == ValueType.STRING:
                # 转换为字符串
                if isinstance(value.value, (dict, list)):
                    import json
                    converted_value.value = json.dumps(value.value)
                else:
                    converted_value.value = str(value.value)
                    
            elif value.type == ValueType.BOOL:
                # 转换为布尔值
                if isinstance(value.value, str):
                    lower_value = value.value.lower().strip()
                    if lower_value in ('true', '1', 'yes', 'on'):
                        converted_value.value = True
                    elif lower_value in ('false', '0', 'no', 'off'):
                        converted_value.value = False
                    else:
                        converted_value.value = bool(value.value)
                else:
                    converted_value.value = bool(value.value)
                    
            elif value.type == ValueType.LIST:
                # 转换为列表
                if isinstance(value.value, str):
                    import json
                    try:
                        converted_value.value = json.loads(value.value)
                        if not isinstance(converted_value.value, list):
                            # 如果不是列表，尝试按逗号分割
                            converted_value.value = [item.strip() for item in value.value.split(',') if item.strip()]
                    except json.JSONDecodeError:
                        # 按逗号分割
                        converted_value.value = [item.strip() for item in value.value.split(',') if item.strip()]
                elif isinstance(value.value, list):
                    converted_value.value = value.value
                else:
                    converted_value.value = [value.value]
                    
            elif value.type == ValueType.DICT:
                # 转换为字典
                if isinstance(value.value, str):
                    import json
                    try:
                        converted_value.value = json.loads(value.value)
                        if not isinstance(converted_value.value, dict):
                            raise ValueError(f"解析后的值不是字典类型: {type(converted_value.value)}")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析JSON字典: {e}")
                elif isinstance(value.value, dict):
                    converted_value.value = value.value
                else:
                    raise ValueError(f"无法将 {type(value.value)} 转换为字典")
                    
            else:
                # 对于其他类型，保持原值
                converted_value.value = value.value
                
        except (ValueError, TypeError, ImportError) as e:
            raise ValueError(f"无法将值 '{value.value}' 转换为类型 '{value.type.value}': {str(e)}")
            
        return converted_value

    async def _process_condition(self, condition: Condition, call_vars: CallVars, 
                                 branch_id: str) -> tuple[bool, str]:
        """处理单个条件
        
        Args:
            condition: 需要处理的条件
            call_vars: Call变量
            branch_id: 分支ID，用于日志记录
            
        Returns:
            tuple[bool, str]: (是否成功, 错误消息)
        """
        # 处理左值
        success, _left, error_msg = await self._process_condition_value(
            condition.left, call_vars, branch_id, "左值")
        if not success:
            return False, error_msg
            
        # 处理右值
        success, _right, error_msg = await self._process_condition_value(
            condition.right, call_vars, branch_id, "右值")
        if not success:
            return False, error_msg

        # 更新条件对象中的解析后的值
        condition.left = _left
        condition.right = _right

        # 检查运算符是否有效
        if condition.operate is None:
            return False, "条件缺少运算符"
        
        # 根据运算符确定期望的值类型
        try:
            expected_type = ConditionHandler.get_value_type_from_operate(condition.operate)
        except Exception as e:
            return False, f"不支持的运算符: {condition.operate}"
        
        # 检查类型是否与运算符匹配
        if not expected_type == _left.type == _right.type:
            return False, f"左值类型 {_left.type.value} 与运算符 {condition.operate} 不匹配"
                
        return True, ""

    async def _process_branch(self, choice: ChoiceBranch, call_vars: CallVars) -> tuple[bool, list[str]]:
        """处理单个分支
        
        Args:
            choice: 需要处理的分支
            call_vars: Call变量
            
        Returns:
            tuple[bool, list[str]]: (是否成功, 错误消息列表)
        """
        # 验证逻辑运算符
        if not self._validate_branch_logic(choice):
            return False, ["无效的逻辑运算符"]
            
        valid_conditions = []
        error_messages = []
        
        # 处理每个条件
        for condition_original in choice.conditions:
            condition = copy.deepcopy(condition_original)
            success, error_msg = await self._process_condition(condition, call_vars, choice.branch_id)
            
            if success:
                valid_conditions.append(condition)
            else:
                error_messages.append(error_msg)
                logger.warning(f"[Choice] 分支 {choice.branch_id} 条件处理失败: {error_msg}")
        
        # 如果没有有效条件，返回失败
        if not valid_conditions and not choice.is_default:
            error_messages.append("分支没有有效条件")
            return False, error_messages
            
        # 更新有效条件
        choice.conditions = valid_conditions
        return True, []

    async def _prepare_message(self, call_vars: CallVars) -> list[ChoiceBranch]:
        """替换choices中的系统变量
        
        Args:
            call_vars: Call变量
            
        Returns:
            list[ChoiceBranch]: 处理后的有效分支列表
        """
        valid_choices = []
        for choice in self.choices:
            try:
                success, error_messages = await self._process_branch(choice, call_vars)
                
                if success:
                    valid_choices.append(choice)
                else:
                    logger.warning(f"[Choice] 分支 {choice.branch_id} 处理失败: {'; '.join(error_messages)}")
                    
            except Exception as e:
                logger.warning(f"[Choice] 分支 {choice.branch_id} 处理失败: {e}，已跳过")
                continue

        return valid_choices

    async def _init(self, call_vars: CallVars) -> ChoiceInput:
        """初始化Choice工具"""
        return ChoiceInput(
            choices=await self._prepare_message(call_vars),
        )

    async def _exec(
        self, input_data: dict[str, Any]
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行Choice工具"""
        # 解析输入数据
        data = ChoiceInput(**input_data)
        try:
            branch_id = ConditionHandler.handler(data.choices)
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=ChoiceOutput(branch_id=branch_id).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception as e:
            raise CallError(message=f"选择工具调用失败：{e!s}", data={}) from e
