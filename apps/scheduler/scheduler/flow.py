"""Scheduler中，关于Flow的逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.entities.task import RequestDataPlugin
from apps.llm.patterns import Select
from apps.scheduler.pool.pool import Pool


async def choose_flow(task_id: str, question: str, origin_plugin_list: list[RequestDataPlugin]) -> tuple[str, Optional[RequestDataPlugin]]:
    """依据用户的输入和选择，构造对应的Flow。

    - 当用户没有选择任何Plugin时，直接进行智能问答
    - 当用户选择auto时，自动识别最合适的n个Plugin，并在其中挑选flow
    - 当用户选择Plugin时，在plugin内挑选最适合的flow

    :param question: 用户输入（用户问题）
    :param origin_plugin_list: 用户选择的插件，可以一次选择多个
    :result: 经LLM选择的Plugin ID和Flow ID
    """
    # 去掉无效的插件选项：plugin_id为空
    plugin_ids = []
    flow_ids = []
    for item in origin_plugin_list:
        if not item.plugin_id:
            continue
        plugin_ids.append(item.plugin_id)
        if item.flow_id:
            flow_ids.append(item)

    # 用户什么都不选，直接智能问答
    if len(plugin_ids) == 0:
        return "", None

    # 用户只选了auto
    if len(plugin_ids) == 1 and plugin_ids[0] == "auto":
        # 用户要求自动识别
        plugin_top = Pool().get_k_plugins(question)
        # 聚合插件的Flow
        plugin_ids = [str(plugin.name) for plugin in plugin_top]

    # 用户固定了Flow的ID
    if len(flow_ids) > 0:
        # 直接使用对应的Flow，不选择
        return plugin_ids[0], flow_ids[0]

    # 用户选了插件
    flows = Pool().get_k_flows(question, plugin_ids)

    # 使用大模型选择Top1 Flow
    flow_list = [{
        "name": str(item.plugin) + "/" + str(item.name),
        "description": str(item.description),
    } for item in flows]

    if len(plugin_ids) == 1 and plugin_ids[0] == "auto":
        # 用户选择自动识别时，包含智能问答
        flow_list += [{
            "name": "KnowledgeBase",
            "description": "当上述工具无法直接解决用户问题时，使用知识库进行回答。",
        }]

    # 返回top1 Flow的ID
    selected_id = await Select().generate(task_id=task_id, choices=flow_list, question=question)
    if selected_id == "KnowledgeBase":
        return "", None

    plugin_id = selected_id.split("/")[0]
    flow_id = selected_id.split("/")[1]
    return plugin_id, RequestDataPlugin(
        plugin_id=plugin_id,
        flow_id=flow_id,
        params={},
        auth={},
    )
