"""Scheduler中，关于Flow的逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.entities.flow import Flow
from apps.entities.task import RequestDataApp
from apps.llm.patterns import Select
from apps.scheduler.pool.pool import Pool


class PredifinedRAGFlow(Flow):
    """预定义的RAG Flow"""

    name: str = "KnowledgeBase"
    description: str = "当上述工具无法直接解决用户问题时，使用知识库进行回答。"


class FlowChooser:
    """Flow选择器"""

    def __init__(self, task_id: str, question: str, user_selected: Optional[RequestDataApp] = None):
        """初始化Flow选择器"""
        self._task_id = task_id
        self._question = question
        self._user_selected = user_selected


    def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        pass


    def choose_flow(self) -> Optional[RequestDataApp]:
        """依据用户的输入和选择，构造对应的Flow。

        - 当用户没有选择任何app时，直接进行智能问答
        - 当用户选择了特定的app时，在plugin内挑选最适合的flow
        """
        if not self._user_selected or not self._user_selected.app_id:
            return None

        if self._user_selected.flow_id:
            return self._user_selected

        top_flow = self.get_top_flow()
        if top_flow == "KnowledgeBase":
            return None

        return RequestDataApp(
            appId=self._user_selected.app_id,
            flowId=top_flow,
            params={},
        )
