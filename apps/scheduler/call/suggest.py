"""用于问题推荐的工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar, Optional

import ray
from pydantic import BaseModel, Field

from apps.entities.scheduler import CallError, CallVars
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall


class _SingleFlowSuggestionConfig(BaseModel):
    """涉及单个Flow的问题推荐配置"""

    flow_id: str
    question: Optional[str] = Field(default=None, description="固定的推荐问题")


class _SuggestionOutputItem(BaseModel):
    """问题推荐结果的单个条目"""

    question: str
    app_id: str
    flow_id: str
    flow_description: str


class SuggestionOutput(BaseModel):
    """问题推荐结果"""

    output: list[_SuggestionOutputItem]


class Suggestion(CoreCall, ret_type=SuggestionOutput):
    """问题推荐"""

    name: ClassVar[str] = "问题推荐"
    description: ClassVar[str] = "在答案下方显示推荐的下一个问题"

    configs: list[_SingleFlowSuggestionConfig] = Field(description="问题推荐配置", min_length=1)
    num: int = Field(default=3, ge=1, le=6, description="推荐问题的总数量（必须大于等于configs中涉及的Flow的数量）")


    async def init(self, syscall_vars: CallVars, **_kwargs: Any) -> dict[str, Any]:
        """初始化"""
        # 普通变量
        self._question = syscall_vars.question
        self._task_id = syscall_vars.task_id
        self._background = syscall_vars.summary
        self._user_sub = syscall_vars.user_sub

        return {
            "question": self._question,
            "task_id": self._task_id,
            "background": self._background,
            "user_sub": self._user_sub,
        }


    async def exec(self) -> dict[str, Any]:
        """运行问题推荐"""
        # 获取当前任务
        task_actor = await ray.get_actor("task")
        task = await task_actor.get_task.remote(self._task_id)

        # 获取当前用户的画像
        user_domain = await UserDomainManager.get_user_domain_by_user_sub_and_topk(self._user_sub, 5)

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

        return {}
