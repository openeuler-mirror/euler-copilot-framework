"""Scheduler中，关于Flow的逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.entities.task import RequestDataApp
from apps.llm.patterns import Select
from apps.scheduler.pool.pool import Pool


async def choose_flow(task_id: str, question: str, origin_app: RequestDataApp) -> tuple[str, Optional[RequestDataApp]]:
    """依据用户的输入和选择，构造对应的Flow。

    - 当用户没有选择任何Plugin时，直接进行智能问答
    - 当用户选择auto时，自动识别最合适的n个Plugin，并在其中挑选flow
    - 当用户选择Plugin时，在plugin内挑选最适合的flow

    :param question: 用户输入（用户问题）
    :param origin_app: 用户选择的app信息
    :result: 经LLM选择的App ID和Flow ID
    """
    # TODO: 根据用户选择的App，选一次top_k flow
    return "", None