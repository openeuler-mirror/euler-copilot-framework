"""Scheduler中，关于Flow的逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
from typing import Optional

import ray

from apps.constants import LOGGER
from apps.entities.flow import Flow
from apps.entities.task import RequestDataApp
from apps.llm.patterns import Select


class PredifinedRAGFlow(Flow):
    """预定义的RAG Flow"""

    name: str = "KnowledgeBase"
    description: str = "当上述工具无法直接解决用户问题时，使用知识库进行回答。"


class FlowChooser:
    """Flow选择器"""

    def __init__(self, task_id: str, question: str, user_selected: Optional[RequestDataApp] = None) -> None:
        """初始化Flow选择器"""
        self._task_id = task_id
        self._question = question
        self._user_selected = user_selected


    async def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        LOGGER.info(f"[FlowChooser] Judging top flow for task {self._task_id}...")
        pool = ray.get_actor("pool")
        # 获取所选应用的所有Flow
        if not self._user_selected or not self._user_selected.app_id:
            return "KnowledgeBase"

        flow_list = await asyncio.gather(pool.get_flow_list.remote(self._user_selected.app_id))[0]
        if not flow_list:
            return "KnowledgeBase"

        LOGGER.info(f"[FlowChooser] Selecting top flow for task {self._task_id}...")
        return await Select().generate(self._task_id, question=self._question, choices=flow_list)


    async def choose_flow(self) -> Optional[RequestDataApp]:
        """依据用户的输入和选择，构造对应的Flow。

        - 当用户没有选择任何app时，直接进行智能问答
        - 当用户选择了特定的app时，在plugin内挑选最适合的flow
        """
        if not self._user_selected or not self._user_selected.app_id:
            return None

        if self._user_selected.flow_id:
            return self._user_selected

        top_flow = await self.get_top_flow()
        if top_flow == "KnowledgeBase":
            return None

        return RequestDataApp(
            appId=self._user_selected.app_id,
            flowId=top_flow,
            params={},
        )
