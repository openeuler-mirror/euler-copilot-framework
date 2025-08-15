# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""变量赋值Call"""

import logging
import math
from collections.abc import AsyncGenerator
from typing import Any

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.variable_assign.schema import (
    VariableAssignInput,
    VariableAssignOutput,
    VariableOperation,
    StringOperation,
    NumberOperation,
    ArrayOperation,
)
from apps.scheduler.variable.type import VariableType
from apps.scheduler.variable.pool_manager import get_pool_manager
from apps.schemas.enum_var import CallType
from apps.schemas.scheduler import CallInfo, CallVars, CallOutputChunk, CallOutputType, CallError


logger = logging.getLogger(__name__)


class VariableAssign(CoreCall, input_model=VariableAssignInput, output_model=VariableAssignOutput):
    """变量赋值Call"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._call_vars = None

    @classmethod
    def info(cls) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        return CallInfo(
            name="变量赋值",
            type=CallType.TRANSFORM,
            description="对已有变量进行值的操作，支持字符串、数值和数组类型变量的多种操作"
        )

    async def _init(self, call_vars: CallVars) -> VariableAssignInput:
        """
        初始化Call

        :param CallVars call_vars: 由Executor传入的变量，包含当前运行信息
        :return: Call的输入
        :rtype: VariableAssignInput
        """
        # 保存CallVars以便在_exec中使用
        self._call_vars = call_vars
        
        # 从实例属性中获取operations（已通过StepExecutor扁平化处理）
        operations = getattr(self, 'operations', [])
        
        return VariableAssignInput(
            operations=operations,
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """
        执行变量赋值操作

        :param dict[str, Any] input_data: 填充后的Call的最终输入
        """
        try:
            # 获取CallVars从实例属性
            call_vars = getattr(self, '_call_vars', None)
            if not call_vars:
                raise CallError(
                    message="无法获取调用上下文",
                    data={}
                )
            
            results = []  # 记录执行结果
            
            # 优先处理 operations 数组（从input_data中获取）
            operations = input_data.get('operations', None)
            logger.info(f"开始执行 {len(operations)} 个变量操作")
            for i, operation in enumerate(operations):
                try:
                    result = await self._execute_single_operation(operation, call_vars)
                    results.append({
                        "index": i + 1,
                        "status": "success",
                        "variable_name": operation.get('variable_name') if isinstance(operation, dict) else operation.variable_name,
                        "operation": operation.get('operation') if isinstance(operation, dict) else operation.operation,
                        "result": result
                    })
                    logger.debug(f"第 {i+1} 个操作执行成功")
                except Exception as e:
                    error_info = {
                        "index": i + 1,
                        "status": "error",
                        "variable_name": operation.get('variable_name') if isinstance(operation, dict) else operation.variable_name,
                        "operation": operation.get('operation') if isinstance(operation, dict) else operation.operation,
                        "error": str(e)
                    }
                    results.append(error_info)
                    logger.error(f"第 {i+1} 个操作执行失败: {e}")
                    # 继续执行其他操作，不中断
                    continue
            
            # 成功完成时 yield 结果
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=VariableAssignOutput().model_dump(by_alias=True, exclude_none=True)
            )
                
        except Exception as e:
            if isinstance(e, CallError):
                raise  # 重新抛出 CallError，让 StepExecutor 处理
            else:
                logger.error(f"变量赋值操作失败: {e}")
                raise CallError(
                    message=f"变量赋值操作失败: {e}",
                    data={}
                ) from e

    async def _execute_single_operation(self, operation, call_vars) -> dict[str, Any]:
        """
        执行单个变量操作
        
        :param operation: 变量操作对象或字典
        :param call_vars: 调用上下文
        :return: 操作结果
        """
        
        try:
            # 兼容处理：如果是字典则转换为属性访问
            if isinstance(operation, dict):
                variable_name = operation.get('variable_name')
                op_type = operation.get('operation')
                value = operation.get('value')
                variable_type = operation.get('variable_type')
                is_value_reference = operation.get('is_value_reference', False)
            else:
                # 如果是 VariableOperation 对象
                variable_name = operation.variable_name
                op_type = operation.operation
                value = operation.value
                variable_type = getattr(operation, 'variable_type', None)
                is_value_reference = getattr(operation, 'is_value_reference', False)
            
            if not variable_name:
                raise CallError(
                    message="变量名称不能为空",
                    data={}
                )
            
            if not op_type:
                raise CallError(
                    message="操作类型不能为空",
                    data={}
                )
            
            # 如果值是变量引用，需要解析引用
            if is_value_reference and value:
                value = await self._resolve_variable_reference(value, call_vars)
            
            # 执行变量操作
            await self._execute_variable_operation(
                variable_name, op_type, value, call_vars
            )
            
            return {
                "variable_name": variable_name,
                "operation": op_type,
                "value": value,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"执行单个变量操作失败: {e}")
            raise

    async def _resolve_variable_reference(self, variable_reference: str, call_vars) -> Any:
        """
        解析变量引用，获取变量的实际值
        
        :param variable_reference: 变量引用字符串
        :param call_vars: 调用上下文
        :return: 解析后的变量值
        """
        try:
            # 使用统一的变量解析逻辑，支持更复杂的引用格式
            from apps.scheduler.variable.integration import VariableIntegration
            
            resolved_value, _ = await VariableIntegration.resolve_variable_reference(
                reference=variable_reference,
                user_sub=call_vars.ids.user_sub,
                flow_id=call_vars.ids.flow_id,
                conversation_id=call_vars.ids.conversation_id,
                current_step_id=getattr(self, '_step_id', None)
            )
            
            return resolved_value
            
        except Exception as e:
            logger.warning(f"变量引用 '{variable_reference}' 未找到，使用原始值")
            return variable_reference

    async def _execute_variable_operation(
        self, variable_name: str, operation: str, value: Any, call_vars: CallVars
    ) -> None:
        """
        执行具体的变量操作

        :param variable_name: 变量名称
        :param operation: 操作类型
        :param value: 操作值
        :param call_vars: 调用上下文
        :return: 操作结果
        """
        try:
            # 解析变量名，支持 conversation.test 格式
            actual_variable_name, target_scope = self._parse_variable_name(variable_name)
            
            # 获取变量当前值和类型
            pool_manager = await get_pool_manager()
            
            old_variable = None
            
            # 根据解析出的作用域查找变量
            if target_scope == "conversation":
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        old_variable = await conversation_pool.get_variable(actual_variable_name)
            elif target_scope == "user":
                if call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        old_variable = await user_pool.get_variable(actual_variable_name)
            elif target_scope == "environment" or target_scope == "system":
                if call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        old_variable = await flow_pool.get_variable(actual_variable_name)
            else:
                # 没有明确作用域，按原有逻辑依次查找
                # 首先尝试从对话变量中获取
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        old_variable = await conversation_pool.get_variable(actual_variable_name)
                
                # 如果对话变量中没有，尝试从用户变量中获取
                if not old_variable and call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        old_variable = await user_pool.get_variable(actual_variable_name)
                
                # 如果用户变量中也没有，尝试从环境变量中获取
                if not old_variable and call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        old_variable = await flow_pool.get_variable(actual_variable_name)
            
            if not old_variable:
                raise CallError(
                    message=f"变量 '{variable_name}' 不存在",
                    data={"variable_name": variable_name, "actual_name": actual_variable_name, "scope": target_scope}
                )
            
            old_value = old_variable.value
            var_type = old_variable.var_type
            
            # 根据变量类型执行不同的操作
            if var_type == VariableType.STRING:
                new_value = await self._execute_string_operation(old_value, operation, value)
            elif var_type == VariableType.NUMBER:
                new_value = await self._execute_number_operation(old_value, operation, value)
            elif var_type.is_array_type():
                new_value = await self._execute_array_operation(old_value, operation, value, var_type)
            else:
                raise CallError(
                    message=f"不支持的变量类型: {var_type}",
                    data={"variable_name": variable_name, "variable_type": str(var_type)}
                )
            
            # 更新变量值
            success = await self._update_variable_value(
                actual_variable_name, new_value, call_vars, target_scope
            )
            
            if success:
                logger.info(f"变量 '{variable_name}' 操作 '{operation}' 执行成功，从 {old_value} 更新为 {new_value}")
            else:
                raise CallError(
                    message=f"变量 '{variable_name}' 更新失败",
                    data={"variable_name": variable_name, "actual_name": actual_variable_name, "scope": target_scope}
                )
                
        except Exception as e:
            if isinstance(e, CallError):
                raise  # 重新抛出 CallError
            else:
                logger.error(f"执行变量操作失败: {e}")
                raise CallError(
                    message=f"执行变量操作失败: {e}",
                    data={"variable_name": variable_name, "operation": operation}
                ) from e

    def _parse_variable_name(self, variable_name: str) -> tuple[str, str | None]:
        """
        解析变量名，支持 conversation.test、user.config 等格式
        
        :param variable_name: 原始变量名
        :return: (实际变量名, 目标作用域)
        """
        if "." not in variable_name:
            return variable_name, None
        
        parts = variable_name.split(".", 1)
        scope_part = parts[0].lower()
        actual_name = parts[1]
        
        # 支持的作用域前缀
        valid_scopes = ["conversation", "user", "environment", "system"]
        
        if scope_part in valid_scopes:
            return actual_name, scope_part
        else:
            # 如果不是有效的作用域前缀，就把整个字符串当作变量名
            return variable_name, None

    async def _execute_string_operation(self, old_value: Any, operation: str, value: Any) -> str:
        """执行字符串类型变量操作"""
        if operation == StringOperation.OVERWRITE:
            return str(value) if value is not None else ""
        elif operation == StringOperation.CLEAR:
            return ""
        else:
            raise ValueError(f"字符串类型不支持操作: {operation}")

    async def _execute_number_operation(self, old_value: Any, operation: str, value: Any) -> float:
        """执行数值类型变量操作"""
        old_num = float(old_value) if old_value is not None else 0.0
        
        if operation == NumberOperation.OVERWRITE:
            return float(value) if value is not None else 0.0
        elif operation == NumberOperation.CLEAR:
            return 0.0
        elif operation == NumberOperation.ADD:
            return old_num + float(value)
        elif operation == NumberOperation.SUBTRACT:
            return old_num - float(value)
        elif operation == NumberOperation.MULTIPLY:
            return old_num * float(value)
        elif operation == NumberOperation.DIVIDE:
            if float(value) == 0:
                raise ValueError("除数不能为零")
            return old_num / float(value)
        elif operation == NumberOperation.MODULO:
            if float(value) == 0:
                raise ValueError("模数不能为零")
            return old_num % float(value)
        elif operation == NumberOperation.POWER:
            return math.pow(old_num, float(value))
        elif operation == NumberOperation.SQRT:
            if old_num < 0:
                raise ValueError("不能对负数开方")
            return math.sqrt(old_num)
        else:
            raise ValueError(f"数值类型不支持操作: {operation}")

    async def _execute_array_operation(self, old_value: Any, operation: str, value: Any, var_type: VariableType) -> list:
        """执行数组类型变量操作"""
        old_array = old_value if isinstance(old_value, list) else []
        element_type = var_type.get_array_element_type()
        
        if operation == ArrayOperation.OVERWRITE:
            if not isinstance(value, list):
                raise ValueError("覆盖操作需要提供数组值")
            return await self._validate_array_elements(value, element_type)
        elif operation == ArrayOperation.CLEAR:
            return []
        elif operation == ArrayOperation.APPEND:
            await self._validate_single_element(value, element_type)
            new_array = old_array.copy()
            new_array.append(value)
            return new_array
        elif operation == ArrayOperation.EXTEND:
            if not isinstance(value, list):
                raise ValueError("扩展操作需要提供数组值")
            validated_elements = await self._validate_array_elements(value, element_type)
            new_array = old_array.copy()
            new_array.extend(validated_elements)
            return new_array
        elif operation == ArrayOperation.POP_FIRST:
            if not old_array:
                raise ValueError("数组为空，无法移除首项")
            new_array = old_array.copy()
            new_array.pop(0)
            return new_array
        elif operation == ArrayOperation.POP_LAST:
            if not old_array:
                raise ValueError("数组为空，无法移除尾项")
            new_array = old_array.copy()
            new_array.pop()
            return new_array
        else:
            raise ValueError(f"数组类型不支持操作: {operation}")

    async def _validate_single_element(self, element: Any, element_type: VariableType) -> None:
        """验证单个数组元素的类型"""
        if element_type == VariableType.STRING and not isinstance(element, str):
            raise ValueError("字符串数组只能添加字符串元素")
        elif element_type == VariableType.NUMBER and not isinstance(element, (int, float)):
            raise ValueError("数值数组只能添加数值元素")
        elif element_type == VariableType.FILE and not isinstance(element, str):
            # 文件类型通常以字符串路径表示
            raise ValueError("文件数组只能添加文件路径字符串")

    async def _validate_array_elements(self, elements: list, element_type: VariableType) -> list:
        """验证数组元素的类型一致性"""
        for element in elements:
            await self._validate_single_element(element, element_type)
        return elements

    async def _update_variable_value(self, variable_name: str, new_value: Any, call_vars: CallVars, target_scope: str | None = None) -> bool:
        """更新变量值"""
        try:
            pool_manager = await get_pool_manager()
            
            # 如果指定了目标作用域，优先在该作用域更新
            if target_scope == "conversation":
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        try:
                            await conversation_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"对话变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"对话变量 {variable_name} 更新失败: {e}")
                            raise CallError(
                                message=f"对话变量 {variable_name} 更新失败: {e}",
                                data={"variable_name": variable_name, "scope": "conversation"}
                            ) from e
                else:
                    raise CallError(
                        message="无法更新对话变量：缺少 conversation_id",
                        data={"variable_name": variable_name, "scope": "conversation"}
                    )
            elif target_scope == "user":
                if call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        try:
                            await user_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"用户变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"用户变量 {variable_name} 更新失败: {e}")
                            raise CallError(
                                message=f"用户变量 {variable_name} 更新失败: {e}",
                                data={"variable_name": variable_name, "scope": "user"}
                            ) from e
                else:
                    raise CallError(
                        message="无法更新用户变量：缺少 user_sub",
                        data={"variable_name": variable_name, "scope": "user"}
                    )
            elif target_scope in ["environment", "system"]:
                if call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        try:
                            await flow_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"环境变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"环境变量 {variable_name} 更新失败: {e}")
                            raise CallError(
                                message=f"环境变量 {variable_name} 更新失败: {e}",
                                data={"variable_name": variable_name, "scope": target_scope}
                            ) from e
                else:
                    raise CallError(
                        message="无法更新环境变量：缺少 flow_id",
                        data={"variable_name": variable_name, "scope": target_scope}
                    )
            else:
                # 没有指定作用域，按原有逻辑依次尝试更新
                # 首先尝试更新对话变量
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        try:
                            await conversation_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"对话变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"对话变量 {variable_name} 更新失败: {e}")
                
                # 如果对话变量更新失败，尝试更新用户变量
                if call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        try:
                            await user_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"用户变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"用户变量 {variable_name} 更新失败: {e}")
                
                # 如果用户变量也更新失败，尝试更新环境变量
                if call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        try:
                            await flow_pool.update_variable(variable_name, value=new_value)
                            logger.debug(f"环境变量 {variable_name} 更新成功")
                            return True
                        except Exception as e:
                            logger.debug(f"环境变量 {variable_name} 更新失败: {e}")
            
            return False
        except Exception as e:
            if isinstance(e, CallError):
                raise  # 重新抛出 CallError
            else:
                logger.error(f"更新变量值失败: {e}")
                raise CallError(
                    message=f"更新变量值失败: {e}",
                    data={"variable_name": variable_name, "scope": target_scope}
                ) from e
