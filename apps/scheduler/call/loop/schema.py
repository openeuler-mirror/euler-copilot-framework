# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""循环节点的数据结构"""

from typing import Any
import uuid

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase
from apps.scheduler.call.choice.schema import Condition, Logic


class LoopStopCondition(DataBase):
    """循环停止条件，类似ChoiceBranch但无需branch_id和is_default"""
    
    logic: Logic = Field(description="逻辑运算符", default=Logic.AND)
    conditions: list[Condition] = Field(description="条件列表", default=[])


class LoopInput(DataBase):
    """循环节点的输入"""
    
    variables: dict[str, Any] = Field(description="循环变量，保存flow时会自动创建对话变量模板conversation.{step_id}.k=v供后续节点引用", default={})
    stop_condition: LoopStopCondition = Field(description="循环终止条件", default=LoopStopCondition())
    max_iteration: int = Field(description="最大循环次数", default=10, ge=1, le=100)
    sub_flow_id: str = Field(description="子工作流ID", default="")


class LoopOutput(DataBase):
    """循环节点的输出"""
    
    iteration_count: int = Field(description="实际执行的循环次数", default=0)
    stop_reason: str = Field(description="停止原因", default="")  # "max_iteration_reached" 或 "condition_met"
    current_iteration: int = Field(description="当前循环次数", default=0)