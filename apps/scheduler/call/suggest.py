"""用于问题推荐的工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

import ray
from pydantic import BaseModel, Field

from apps.entities.scheduler import CallError, CallVars
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall


class _SingleFlowSuggestionConfig(BaseModel):
    """涉及单个Flow的问题推荐配置"""

    flow_id: str
    question: Optional[str] = Field(default=None, description="固定的推荐问题")


class _SuggestInput(BaseModel):
    """用于问题推荐的工具"""

    configs: list[_SingleFlowSuggestionConfig] = Field(description="问题推荐配置", min_length=1)
    num: int = Field(default=3, ge=1, le=6, description="推荐问题的总数量（必须大于等于configs中涉及的Flow的数量）")


class _SuggestionOutputItem(BaseModel):
    """问题推荐结果的单个条目"""

    question: str
    app_id: str
    flow_id: str
    flow_description: str


class _SuggestionOutput(BaseModel):
    """问题推荐结果"""

    output: list[_SuggestionOutputItem]


class Suggestion(metaclass=CoreCall, param_cls=_SuggestInput, output_cls=_SuggestionOutput):
    """问题推荐"""

    name: str = "suggest"
    description: str = "问题推荐"


    async def __call__(self, _slot_data: dict[str, Any]) -> _SuggestionOutput:
        """运行问题推荐"""
        sys_vars: CallVars = getattr(self, "_syscall_vars")
        params: _SuggestInput = getattr(self, "_params")

        # 获取当前任务
        task = await Task.get_task(sys_vars.task_id)

        # 获取当前用户的画像
        user_domain = await UserDomainManager.get_user_domain_by_user_sub_and_topk(sys_vars.user_sub, 5)

        current_record = [
            {
                "role": "user",
                "content": task.record.content.question,
            },
            {
                "role": "assistant",
                "content": task.record.content.answer,
            },
        ]

