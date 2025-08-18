# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用条件控制的循环节点"""

import copy
import logging
import uuid
import asyncio
from collections.abc import AsyncGenerator
from typing import Any, TYPE_CHECKING, ClassVar

from pydantic import Field

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.loop.schema import LoopInput, LoopOutput, LoopStopCondition
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.variable.integration import VariableIntegration
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.flow import Flow, Step, Edge
from apps.schemas.flow_topology import PositionItem
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class Loop(CoreCall, input_model=LoopInput, output_model=LoopOutput):
    """循环节点"""

    to_user: bool = Field(default=False)
    variables: dict[str, Any] = Field(description="循环变量", default={})
    stop_condition: LoopStopCondition = Field(description="循环终止条件", default=LoopStopCondition())
    max_iteration: int = Field(description="最大循环次数", default=10, ge=1, le=100)
    sub_flow_id: str = Field(description="子工作流ID", default="")
    
    # 输出节流相关参数
    output_throttle_interval: float = Field(description="输出节流间隔(秒)", default=0.1)
    progress_report_interval: int = Field(description="进度报告间隔(每N次循环)", default=1)
    
    # 保存传入的CallVars用于子工作流执行
    call_vars: CallVars | None = Field(default=None, exclude=True)
    # 保存StepExecutor引用用于子工作流执行
    step_executor: Any = Field(default=None, exclude=True)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "循环",
            "type": CallType.LOGIC,
            "description": "直到循环终止条件达成或最大循环次数到达之前，子工作流将不断循环执行",
        },
        LanguageType.ENGLISH: {
            "name": "Loop",
            "type": CallType.LOGIC,
            "description": "Subflow will be run repeatly until reaching maximum iteration or matching ending condition",
        },
    }

    async def _process_stop_condition(self, call_vars: CallVars) -> tuple[bool, str]:
        """处理停止条件
        
        Args:
            call_vars: Call变量
            
        Returns:
            tuple[bool, str]: (是否成功处理, 错误消息)
        """
        try:
            # 如果没有条件，默认为有效
            if not self.stop_condition.conditions:
                return True, ""
                
            # 保存原始引用信息的字典
            self._original_references = {}
                
            # 处理每个条件，复用choice.py的逻辑
            valid_conditions = []
            for i, condition_original in enumerate(self.stop_condition.conditions):
                condition = copy.deepcopy(condition_original)
                
                # 处理左值
                success, resolved_left, error_msg = await self._process_condition_value(
                    condition.left, call_vars, "左值")
                if not success:
                    logger.warning(f"[Loop] 停止条件左值处理失败: {error_msg}")
                    continue
                
                # 🔑 保存原始的引用信息，用于后续重新解析
                condition_id = getattr(condition, 'id', f'condition_{i}')
                if condition.left.type.value == 'reference':
                    self._original_references[f'{condition_id}_left'] = condition.left.value
                
                # 处理右值
                success, resolved_right, error_msg = await self._process_condition_value(
                    condition.right, call_vars, "右值")
                if not success:
                    logger.warning(f"[Loop] 停止条件右值处理失败: {error_msg}")
                    continue
                
                # 🔑 保存原始的引用信息，用于后续重新解析
                if condition.right.type.value == 'reference':
                    self._original_references[f'{condition_id}_right'] = condition.right.value
                
                # 更新条件对象中的解析后的值
                condition.left = resolved_left
                condition.right = resolved_right
                
                # 检查运算符是否有效
                if condition.operator is None:
                    logger.warning(f"[Loop] 停止条件缺少运算符")
                    continue
                
                # 根据运算符确定期望的值类型
                try:
                    expected_type = ConditionHandler.get_value_type_from_operate(condition.operator)
                except Exception as e:
                    logger.warning(f"[Loop] 不支持的运算符: {condition.operator}")
                    continue
                
                # 检查类型是否与运算符匹配
                if not expected_type == resolved_left.type == resolved_right.type:
                    logger.warning(f"[Loop] 左值类型 {resolved_left.type.value} 与运算符 {condition.operator} 不匹配")
                    continue
                
                # 验证条件
                left_valid = ConditionHandler.check_value_type(condition.left)
                right_valid = ConditionHandler.check_value_type(condition.right)
                
                if left_valid and right_valid:
                    valid_conditions.append(condition)
                    
            # 更新有效条件
            self.stop_condition.conditions = valid_conditions
            return True, ""
            
        except Exception as e:
            return False, f"停止条件处理失败: {e}"

    async def _process_condition_value(self, value, call_vars: CallVars, value_position: str) -> tuple[bool, Any, str]:
        """处理条件值（左值或右值）- 参考Choice组件的实现
        
        Args:
            value: 需要处理的值对象
            call_vars: Call变量
            value_position: 值的位置描述（"左值"或"右值"）
            
        Returns:
            tuple[bool, Value, str]: (是否成功, 处理后的Value对象，错误消息)
        """
        # 运行时导入避免循环依赖
        from apps.scheduler.call.choice.schema import Value
        from apps.schemas.parameters import ValueType
        
        # 处理reference类型
        if value.type == ValueType.REFERENCE:
            try:
                resolved_value = await self._resolve_single_value(value, call_vars)
            except Exception as e:
                return False, None, f"{value_position}引用解析失败: {e}"
        else:
            resolved_value = value
            
        # 对于非引用类型，先进行类型转换，然后验证值类型（与Choice组件保持一致）
        try:
            converted_value = self._convert_value_to_expected_type(resolved_value)
            resolved_value = converted_value
        except Exception as e:
            return False, None, f"{value_position}类型转换失败: {e}"
            
        # 对于非引用类型，进行类型验证
        is_valid = ConditionHandler.check_value_type(resolved_value)
        
        if not is_valid:
            return False, None, f"{value_position}类型不匹配: {resolved_value.value} 应为 {resolved_value.type}"
            
        return True, resolved_value, ""

    def _convert_value_to_expected_type(self, value) -> Any:
        """根据期望的类型转换值 - 复制自Choice组件
        
        Args:
            value: 需要转换的Value对象
            
        Returns:
            Value: 转换后的Value对象
            
        Raises:
            ValueError: 当值无法转换为指定类型时
        """
        # 运行时导入避免循环依赖
        from apps.scheduler.call.choice.schema import Value
        from apps.schemas.parameters import ValueType
        
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

    async def _check_stop_condition(self) -> bool:
        """检查是否满足停止条件
        
        Returns:
            bool: 是否应该停止循环
        """
        try:
            
            if not self.stop_condition.conditions:
                return False
                
            results = []
            for i, condition in enumerate(self.stop_condition.conditions):
                # 🔑 关键修复：在每次评估时重新解析REFERENCE类型的值
                # 创建条件副本并重新解析引用
                eval_condition = copy.deepcopy(condition)
                
                condition_id = getattr(condition, 'id', f'condition_{i}')
                
                # 重新解析左值如果它是REFERENCE类型
                left_ref_key = f'{condition_id}_left'
                if hasattr(self, '_original_references') and left_ref_key in self._original_references:
                    try:
                        # 运行时导入避免循环依赖
                        from apps.scheduler.call.choice.schema import Value
                        from apps.schemas.parameters import ValueType
                        
                        # 使用原始引用创建新的Value对象进行解析
                        original_ref_value = Value(
                            type=ValueType.REFERENCE,
                            value=self._original_references[left_ref_key]
                        )
                        resolved_left = await self._resolve_single_value(original_ref_value, self.call_vars)
                        eval_condition.left = resolved_left
                    except Exception as e:
                        logger.error(f"[Loop] 左值重新解析失败: {e}")
                
                # 重新解析右值如果它是REFERENCE类型
                right_ref_key = f'{condition_id}_right'
                if hasattr(self, '_original_references') and right_ref_key in self._original_references:
                    try:
                        # 运行时导入避免循环依赖
                        from apps.scheduler.call.choice.schema import Value
                        from apps.schemas.parameters import ValueType
                        
                        # 使用原始引用创建新的Value对象进行解析
                        original_ref_value = Value(
                            type=ValueType.REFERENCE,
                            value=self._original_references[right_ref_key]
                        )
                        resolved_right = await self._resolve_single_value(original_ref_value, self.call_vars)
                        eval_condition.right = resolved_right
                    except Exception as e:
                        logger.error(f"[Loop] 右值重新解析失败: {e}")
                
                # 评估条件
                result = ConditionHandler._judge_condition(eval_condition)
                results.append(result)
            
            # 计算最终结果
            if self.stop_condition.logic.value == "and":
                final_result = all(results)
            elif self.stop_condition.logic.value == "or":
                final_result = any(results)
            else:
                final_result = all(results) if results else False
            
            return final_result
                
        except Exception as e:
            logger.error(f"[Loop] 检查停止条件失败: {e}")
            return False

    def _create_default_sub_flow(self) -> Flow:
        """创建默认的子flow配置（只包含开始和结束节点）
        
        Returns:
            Flow: 默认的子flow配置
        """
        return Flow(
            name="循环子流程",
            description="循环节点的子工作流",
            connectivity=False,
            # 对于嵌入式显示，设置较小的默认焦点区域，方便在循环节点内部显示
            focus_point=PositionItem(x=400.0, y=200.0),  # 更小的默认焦点区域
            debug=False,
            steps={
                "start": Step(
                    node="Empty",
                    type="start",
                    name="开始",
                    description="开始节点",
                    # 针对嵌入式显示调整节点位置，使其更紧凑
                    pos=PositionItem(x=50.0, y=100.0),
                    params={}
                ),
                "end": Step(
                    node="Empty", 
                    type="end",
                    name="结束",
                    description="结束节点",
                    # 结束节点位置也相应调整，保持合理间距
                    pos=PositionItem(x=350.0, y=100.0),
                    params={}
                )
            },
            edges=[]
        )

    async def _create_sub_flow_if_not_exists(self, app_id: str, parent_flow_id: str) -> str:
        """创建子flow如果不存在
        
        Args:
            app_id: 应用ID
            parent_flow_id: 父flow ID
            
        Returns:
            str: 子flow的ID
        """
        if not self.sub_flow_id:
            # 生成新的子flow ID，包含父flow信息以体现关系
            self.sub_flow_id = f"{parent_flow_id}_loop_{str(uuid.uuid4())[:8]}"
            
        # 检查子flow是否已存在
        flow_loader = FlowLoader()
        existing_flow = await flow_loader.load_subflow(app_id, parent_flow_id, self.sub_flow_id)
        
        if not existing_flow:
            # 创建默认子flow配置
            default_flow = self._create_default_sub_flow()
            
            try:
                # 保存子flow到正确的层次化路径
                await flow_loader.save_subflow(app_id, parent_flow_id, self.sub_flow_id, default_flow)
                logger.info(f"[Loop] 创建新的子flow: {self.sub_flow_id}")
            except Exception as e:
                logger.error(f"[Loop] 创建子flow失败: {e}")
                raise CallError(message=f"创建子工作流失败: {e}", data={})
        else:
            logger.info(f"[Loop] 使用现有子flow: {self.sub_flow_id}")
            
        return self.sub_flow_id

    async def _execute_sub_flow(self, iteration: int, call_vars: CallVars, step_executor=None) -> dict[str, Any]:
        """执行子工作流
        
        Args:
            iteration: 当前循环次数
            call_vars: Call变量
            step_executor: 父工作流的StepExecutor，用于访问消息队列
            
        Returns:
            dict[str, Any]: 子工作流的执行结果
        """
        logger.info(f"[Loop] 执行第 {iteration} 次循环，子flow ID: {self.sub_flow_id}")
        
        try:
            # 获取应用ID和父工作流ID
            app_id = call_vars.ids.app_id
            parent_flow_id = call_vars.ids.flow_id
            
            # 加载子工作流
            flow_loader = FlowLoader()
            sub_flow = await flow_loader.load_subflow(app_id, parent_flow_id, self.sub_flow_id)
            
            if not sub_flow:
                logger.warning(f"[Loop] 子工作流不存在: {self.sub_flow_id}")
                # 返回当前变量，不做修改
                return copy.deepcopy(self.variables)
            
            logger.info(f"[Loop] 成功加载子工作流: {sub_flow.name}")
            
            # 开始真正执行子工作流
            updated_variables = copy.deepcopy(self.variables)
            
            # 添加循环相关的系统变量
            updated_variables.update({
                f"loop_iteration_{iteration}": iteration,
                "current_iteration": iteration,
                "sub_flow_executed": True,
                "sub_flow_name": sub_flow.name,
            })
            
            # 执行子工作流中的每个步骤（除了start和end）
            if sub_flow.steps and step_executor:
                await self._execute_sub_flow_steps(sub_flow, step_executor, iteration, updated_variables)
            
            logger.info(f"[Loop] 第 {iteration} 次循环执行完成，处理了 {len(sub_flow.steps)} 个步骤")
            
            return updated_variables
            
        except Exception as e:
            logger.error(f"[Loop] 执行子flow失败: {e}")
            # 发生错误时，返回原变量避免中断循环
            logger.warning(f"[Loop] 由于错误，第 {iteration} 次循环返回原变量")
            return copy.deepcopy(self.variables)
    
    async def _execute_sub_flow_steps(self, sub_flow, step_executor, iteration: int, variables: dict) -> None:
        """执行子工作流中的具体步骤
        
        Args:
            sub_flow: 子工作流对象
            step_executor: 父工作流的StepExecutor
            iteration: 当前循环次数
            variables: 当前变量状态
        """
        from apps.scheduler.executor.step import StepExecutor
        from apps.schemas.task import StepQueueItem
        
        # 保存原始的循环节点状态，确保不被子步骤状态影响
        original_loop_step_id = step_executor.task.state.step_id
        original_loop_step_name = step_executor.task.state.step_name
        original_loop_status = step_executor.task.state.step_status
        
        # 筛选出需要执行的步骤（排除start和end）
        executable_steps = [
            (step_id, step) for step_id, step in sub_flow.steps.items() 
            if step.type not in ['start', 'end']
        ]
        
        logger.info(f"[Loop] 子工作流中有 {len(executable_steps)} 个可执行步骤")
        
        for step_id, step in executable_steps:
            try:
                logger.info(f"[Loop] 执行子工作流步骤: {step.name} (ID: {step_id})")
                
                # 创建步骤队列项
                step_queue_item = StepQueueItem(
                    step_id=step_id,
                    step=step
                )
                
                # 🔑 关键修改：创建独立的任务状态副本，避免影响循环节点本身的状态
                import copy
                sub_task = copy.deepcopy(step_executor.task)
                
                # 创建子步骤执行器，使用独立的任务状态
                sub_step_executor = StepExecutor(
                    task=sub_task,
                    msg_queue=step_executor.msg_queue,
                    background=step_executor.background,
                    question=step_executor.question,
                    step=step_queue_item
                )
                
                # 初始化并运行子步骤
                await sub_step_executor.init()
                
                # 🔑 为子工作流步骤设置独立的状态标识，不影响父循环节点
                sub_step_executor.task.state.step_id = f"loop_{iteration}_{step_id}"
                sub_step_executor.task.state.step_name = f"[循环{iteration}] {step.name}"
                
                # 执行步骤
                await sub_step_executor.run()
                
                logger.info(f"[Loop] 子工作流步骤 {step.name} 执行完成")
                
            except Exception as e:
                logger.error(f"[Loop] 子工作流步骤 {step.name} 执行失败: {e}")
                # 继续执行其他步骤，不中断整个循环
        
        # 🔑 关键修改：确保循环节点的状态完全恢复，不受子步骤影响
        step_executor.task.state.step_id = original_loop_step_id
        step_executor.task.state.step_name = original_loop_step_name
        step_executor.task.state.step_status = original_loop_status
        logger.info(f"[Loop] 已完全恢复循环节点状态: {original_loop_step_name} (ID: {original_loop_step_id})")

    async def _init(self, call_vars: CallVars) -> LoopInput:
        """初始化Loop工具"""
        # 保存call_vars以便后续使用
        self.call_vars = call_vars
        
        # 处理停止条件
        success, error_msg = await self._process_stop_condition(call_vars)
        if not success:
            logger.warning(f"[Loop] 停止条件处理失败: {error_msg}")
            
        # 从call_vars中获取app_id和flow_id（如果可用）
        app_id = getattr(call_vars.ids, 'app_id', 'default')
        flow_id = getattr(call_vars.ids, 'flow_id', 'default')
        
        # 创建子flow
        sub_flow_id = await self._create_sub_flow_if_not_exists(app_id, flow_id)
        
        return LoopInput(
            variables=self.variables,
            stop_condition=self.stop_condition,
            max_iteration=self.max_iteration,
            sub_flow_id=sub_flow_id,
        )
    
    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE) -> AsyncGenerator[CallOutputChunk, None]:
        """重写exec方法来保存executor引用"""
        # 保存executor引用
        self.step_executor = executor
        
        # 调用父类的exec方法
        async for chunk in super().exec(executor, input_data, language):
            yield chunk

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行Loop工具"""
        # 解析输入数据
        data = LoopInput(**input_data)
        
        try:
            iteration_count = 0
            stop_reason = ""
            current_variables = copy.deepcopy(data.variables)
            last_output_time = 0.0
            
            logger.info(f"[Loop] 开始循环执行，最大次数: {data.max_iteration}, 子flow: {data.sub_flow_id}")
            
            # 开始循环
            while iteration_count < data.max_iteration:
                iteration_count += 1
                logger.info(f"[Loop] 开始第 {iteration_count} 次循环")
                
                # 检查停止条件（在执行前检查）
                if await self._check_stop_condition():
                    stop_reason = "condition_met"
                    logger.info(f"[Loop] 满足停止条件，在第 {iteration_count - 1} 次循环后停止")
                    iteration_count -= 1  # 未实际执行这次循环
                    break
                
                # 执行子工作流
                result_variables = await self._execute_sub_flow(iteration_count, self.call_vars, self.step_executor)
                
                # 更新循环变量
                current_variables.update(result_variables)
                self.variables = current_variables
                
                # 检查是否需要输出进度信息（节流机制）
                current_time = asyncio.get_event_loop().time()
                should_output_progress = (
                    iteration_count % self.progress_report_interval == 0 or
                    (current_time - last_output_time) >= self.output_throttle_interval
                )
                
                if should_output_progress and iteration_count < data.max_iteration:
                    # 🔑 发送循环进度事件，确保前端知道循环仍在进行
                    if self.step_executor:
                        from apps.schemas.enum_var import EventType
                        progress_data = {
                            "iteration": iteration_count,
                            "total": data.max_iteration,
                            "status": "running",
                            "current_iteration": iteration_count,
                            "loop_step_name": self.step_executor.task.state.step_name
                        }
                        # 发送循环进度事件，保持循环节点本身的stepId和stepName
                        await self.step_executor.push_message("loop.progress", progress_data)
                    
                    # 输出中间进度信息
                    progress_output = LoopOutput(
                        iteration_count=iteration_count,
                        stop_reason="",
                        current_iteration=iteration_count
                    )
                    
                    yield CallOutputChunk(
                        type=CallOutputType.PROGRESS,
                        content={
                            "iteration": iteration_count,
                            "total": data.max_iteration,
                            "status": "running",
                            "current_iteration": iteration_count
                        },
                    )
                    last_output_time = current_time
                    
                    # 添加短暂延迟，避免过于频繁的输出
                    if self.output_throttle_interval > 0:
                        await asyncio.sleep(self.output_throttle_interval)
                
                # 再次检查停止条件（在执行后检查）
                if await self._check_stop_condition():
                    stop_reason = "condition_met"
                    logger.info(f"[Loop] 满足停止条件，在第 {iteration_count} 次循环后停止")
                    break
                
            # 如果达到最大循环次数
            if iteration_count >= data.max_iteration and not stop_reason:
                stop_reason = "max_iteration_reached"
                logger.info(f"[Loop] 达到最大循环次数 {data.max_iteration}")
                
            # 🔑 关键修改：在循环完成时发送明确的完成事件
            if self.step_executor:
                from apps.schemas.enum_var import EventType
                completion_data = {
                    "iteration_count": iteration_count,
                    "stop_reason": stop_reason,
                    "current_iteration": iteration_count,
                    "status": "completed",
                    "loop_step_name": self.step_executor.task.state.step_name
                }
                # 发送循环完成事件，确保前端知道循环已结束
                await self.step_executor.push_message("loop.completed", completion_data)
                logger.info(f"[Loop] 已发送循环完成事件: {self.step_executor.task.state.step_name}")
            
            # 返回最终结果
            output = LoopOutput(
                iteration_count=iteration_count,
                stop_reason=stop_reason,
                current_iteration=iteration_count
            )
            
            logger.info(f"[Loop] 循环执行完成，执行次数: {iteration_count}, 停止原因: {stop_reason}")
            
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=output.model_dump(exclude_none=True, by_alias=True),
            )
            
        except Exception as e:
            logger.exception(f"[Loop] 循环执行失败: {e}")
            raise CallError(message=f"循环执行失败：{e!s}", data={}) from e
