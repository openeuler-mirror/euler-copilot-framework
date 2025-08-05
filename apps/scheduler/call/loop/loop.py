# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用条件控制的循环节点"""

import copy
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.loop.schema import LoopInput, LoopOutput, LoopStopCondition
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.variable.integration import VariableIntegration
from apps.schemas.enum_var import CallOutputType, CallType
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

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(
            name="循环",
            type=CallType.LOGIC,
            description="直到循环终止条件达成或最大循环次数到达之前，子工作流将不断循环执行"
        )

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
                
            # 处理每个条件，复用choice.py的逻辑
            valid_conditions = []
            for condition_original in self.stop_condition.conditions:
                condition = copy.deepcopy(condition_original)
                
                # 处理左值
                if condition.left.type and hasattr(condition.left, 'value'):
                    try:
                        resolved_left = await self._resolve_single_value(condition.left, call_vars)
                        condition.left = resolved_left
                    except Exception as e:
                        logger.warning(f"[Loop] 停止条件左值解析失败: {e}")
                        continue
                
                # 处理右值
                if condition.right.type and hasattr(condition.right, 'value'):
                    try:
                        resolved_right = await self._resolve_single_value(condition.right, call_vars)
                        condition.right = resolved_right
                    except Exception as e:
                        logger.warning(f"[Loop] 停止条件右值解析失败: {e}")
                        continue
                
                # 验证条件
                if condition.operate and ConditionHandler.check_value_type(condition.left) and ConditionHandler.check_value_type(condition.right):
                    valid_conditions.append(condition)
                    
            # 更新有效条件
            self.stop_condition.conditions = valid_conditions
            return True, ""
            
        except Exception as e:
            return False, f"停止条件处理失败: {e}"

    def _check_stop_condition(self) -> bool:
        """检查是否满足停止条件
        
        Returns:
            bool: 是否应该停止循环
        """
        try:
            if not self.stop_condition.conditions:
                return False
                
            results = []
            for condition in self.stop_condition.conditions:
                result = ConditionHandler._judge_condition(condition)
                results.append(result)
                
            if self.stop_condition.logic.value == "and":
                return all(results)
            elif self.stop_condition.logic.value == "or":
                return any(results)
            else:
                return all(results) if results else False
                
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
        existing_flow = await flow_loader.load(app_id, self.sub_flow_id)
        
        if not existing_flow:
            # 创建默认子flow配置
            default_flow = self._create_default_sub_flow()
            
            try:
                # 保存子flow到文件系统
                await flow_loader.save(app_id, self.sub_flow_id, default_flow)
                logger.info(f"[Loop] 创建新的子flow: {self.sub_flow_id}")
            except Exception as e:
                logger.error(f"[Loop] 创建子flow失败: {e}")
                raise CallError(message=f"创建子工作流失败: {e}", data={})
        else:
            logger.info(f"[Loop] 使用现有子flow: {self.sub_flow_id}")
            
        return self.sub_flow_id

    async def _execute_sub_flow(self, iteration: int, call_vars: CallVars) -> dict[str, Any]:
        """执行子工作流
        
        Args:
            iteration: 当前循环次数
            call_vars: Call变量
            
        Returns:
            dict[str, Any]: 子工作流的执行结果
        """
        logger.info(f"[Loop] 执行第 {iteration} 次循环，子flow ID: {self.sub_flow_id}")
        
        # TODO: 这里需要实现实际的子flow执行逻辑
        # 在实际的实现中，这里应该：
        # 1. 创建一个新的FlowExecutor实例来执行子flow
        # 2. 将当前的循环变量设置到子flow的执行上下文中
        # 3. 执行子flow并获取结果
        # 4. 从结果中提取更新后的变量
        
        # 由于这需要依赖FlowExecutor和完整的执行环境，
        # 现在先返回当前变量作为占位符
        # 在实际集成时，需要调用FlowExecutor来执行子flow
        
        try:
            # 模拟变量更新（实际应该从子flow执行结果中获取）
            updated_variables = copy.deepcopy(self.variables)
            
            # 添加循环相关的系统变量
            updated_variables.update({
                f"loop_iteration_{iteration}": iteration,
                "current_iteration": iteration,
            })
            
            return updated_variables
            
        except Exception as e:
            logger.error(f"[Loop] 执行子flow失败: {e}")
            raise CallError(message=f"执行子工作流失败: {e}", data={})

    async def _init(self, call_vars: CallVars) -> LoopInput:
        """初始化Loop工具"""
        # 处理停止条件
        success, error_msg = await self._process_stop_condition(call_vars)
        if not success:
            logger.warning(f"[Loop] 停止条件处理失败: {error_msg}")
            
        # 从call_vars中获取app_id和flow_id（如果可用）
        app_id = getattr(call_vars.ids, 'app_id', 'default')
        flow_id = getattr(call_vars.state, 'flow_id', 'default')
        
        # 创建子flow
        sub_flow_id = await self._create_sub_flow_if_not_exists(app_id, flow_id)
        
        return LoopInput(
            variables=self.variables,
            stop_condition=self.stop_condition,
            max_iteration=self.max_iteration,
            sub_flow_id=sub_flow_id,
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行Loop工具"""
        # 解析输入数据
        data = LoopInput(**input_data)
        
        try:
            iteration_count = 0
            stop_reason = ""
            current_variables = copy.deepcopy(data.variables)
            
            logger.info(f"[Loop] 开始循环执行，最大次数: {data.max_iteration}, 子flow: {data.sub_flow_id}")
            
            # 开始循环
            while iteration_count < data.max_iteration:
                iteration_count += 1
                logger.info(f"[Loop] 开始第 {iteration_count} 次循环")
                
                # 检查停止条件（在执行前检查）
                if self._check_stop_condition():
                    stop_reason = "condition_met"
                    logger.info(f"[Loop] 满足停止条件，在第 {iteration_count - 1} 次循环后停止")
                    iteration_count -= 1  # 未实际执行这次循环
                    break
                
                # 执行子工作流
                call_vars = CallVars()  # 临时创建，实际需要传入正确的call_vars
                result_variables = await self._execute_sub_flow(iteration_count, call_vars)
                
                # 更新循环变量
                current_variables.update(result_variables)
                self.variables = current_variables
                
                # 再次检查停止条件（在执行后检查）
                if self._check_stop_condition():
                    stop_reason = "condition_met"
                    logger.info(f"[Loop] 满足停止条件，在第 {iteration_count} 次循环后停止")
                    break
                
            # 如果达到最大循环次数
            if iteration_count >= data.max_iteration and not stop_reason:
                stop_reason = "max_iteration_reached"
                logger.info(f"[Loop] 达到最大循环次数 {data.max_iteration}")
                
            # 返回结果
            output = LoopOutput(
                iteration_count=iteration_count,
                stop_reason=stop_reason,
                variables=current_variables
            )
            
            logger.info(f"[Loop] 循环执行完成，执行次数: {iteration_count}, 停止原因: {stop_reason}")
            
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=output.model_dump(exclude_none=True, by_alias=True),
            )
            
        except Exception as e:
            logger.exception(f"[Loop] 循环执行失败: {e}")
            raise CallError(message=f"循环执行失败：{e!s}", data={}) from e
