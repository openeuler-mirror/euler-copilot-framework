"""进行推荐问题生成

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from textwrap import dedent

from apps.common.queue import MessageQueue
from apps.common.security import Security
from apps.constants import LOGGER
from apps.entities.collection import RecordContent
from apps.entities.enum_var import EventType
from apps.entities.message import SuggestContent
from apps.entities.task import RequestDataApp
from apps.llm.patterns.recommend import Recommend
from apps.manager import (
    RecordManager,
    TaskManager,
    UserDomainManager,
)
from apps.scheduler.pool.pool import Pool

# 推荐问题条数
MAX_RECOMMEND = 3
# 用户领域条数
USER_TOP_DOMAINS_NUM = 5
# 历史问题条数
HISTORY_QUESTIONS_NUM = 4


async def plan_next_flow(user_sub: str, task_id: str, queue: MessageQueue, user_selected_plugins: RequestDataApp) -> None:  # noqa: C901, PLR0912
    """生成用户“下一步”Flow的推荐。

    - 若Flow的配置文件中已定义`next_flow[]`字段，则直接使用该字段给定的值
    - 否则，使用LLM进行选择。将根据用户的插件选择情况限定范围

    选择“下一步”Flow后，根据当前Flow的执行结果和“下一步”Flow的描述，生成改写的或预测的问题。

    :param summary: 上下文总结，包含当前Flow的执行结果。
    :param current_flow_name: 当前执行的Flow的Name，用于避免重复选择同一个Flow
    :param user_selected_plugins: 用户选择的插件列表，用于限定推荐范围
    :return: 列表，包含“下一步”Flow的Name和预测问题
    """
    task = await TaskManager.get_task(task_id)
    # 获取当前用户的领域
    user_domain = await UserDomainManager.get_user_domain_by_user_sub_and_topk(user_sub, USER_TOP_DOMAINS_NUM)
    current_record = dedent(f"""
        Question: {task.record.content.question}
        Answer: {task.record.content.answer}
    """)
    generated_questions = ""

    records = await RecordManager.query_record_by_conversation_id(user_sub, task.record.conversation_id, HISTORY_QUESTIONS_NUM)
    last_n_questions = ""
    for i, record in enumerate(records):
        data = RecordContent.model_validate(json.loads(Security.decrypt(record.data, record.key)))
        last_n_questions += f"Question {i+1}: {data.question}\n"

    if task.flow_state is None:
        # 当前没有使用Flow，进行普通推荐
        for _ in range(MAX_RECOMMEND):
            question = await Recommend().generate(
                task_id=task_id,
                history_questions=last_n_questions,
                recent_question=current_record,
                user_preference=user_domain,
                shown_questions=generated_questions,
            )
            generated_questions += f"{question}\n"
            content = SuggestContent(
                question=question,
                appId="",
                flowId="",
                flowDescription="",
            )
            await queue.push_output(event_type=EventType.SUGGEST, data=content.model_dump(exclude_none=True, by_alias=True))
        return

    # 当前使用了Flow
    flow_id = task.flow_state.name
    app_id = task.flow_state.app_id
    return
    # TODO: 推荐flow待完善
    # _, flow_data = Pool().get_flow(flow_id, app_id)
    # if flow_data is None:
    #     err = "Flow数据不存在"
    #     raise ValueError(err)

    # if flow_data.next_flow is None:
    #     # 根据用户选择的插件，选一次top_k flow
    #     app_ids = []
    #     for plugin in user_selected_plugins:
    #         if plugin.app_id and plugin.app_id not in app_ids:
    #             app_ids.append(plugin.app_id)
    #     result = Pool().get_k_flows(task.record.content.question, app_ids)
    #     for i, flow in enumerate(result):
    #         if i >= MAX_RECOMMEND:
    #             break
    #         # 改写问题
    #         rewrite_question = await Recommend().generate(
    #             task_id=task_id,
    #             action_description=flow.description,
    #             history_questions=last_n_questions,
    #             recent_question=current_record,
    #             user_preference=str(user_domain),
    #             shown_questions=generated_questions,
    #         )
    #         generated_questions += f"{rewrite_question}\n"

    #         content = SuggestContent(
    #             app_id=app_id,
    #             flow_id=flow_id,
    #             flow_description=str(flow.description),
    #             question=rewrite_question,
    #         )
    #         await queue.push_output(event_type=EventType.SUGGEST, data=content.model_dump(exclude_none=True, by_alias=True))
    #     return

    # # 当前有next_flow
    # for i, next_flow in enumerate(flow_data.next_flow):
    #     # 取前MAX_RECOMMEND个Flow，保持顺序
    #     if i >= MAX_RECOMMEND:
    #         break

    #     if next_flow.plugin is not None:
    #         next_flow_app_id = next_flow.plugin
    #     else:
    #         next_flow_app_id = app_id

    #     flow_metadata, _ = next_flow.id, next_flow_app_id,
    #     # flow_metadata, _ = Pool().get_flow(
    #     #     next_flow.id,
    #     #     next_flow_app_id,
    #     # )

    #     # flow不合法
    #     if flow_metadata is None:
    #         LOGGER.error(f"Flow {next_flow.id} in {next_flow_app_id} not found")
    #         continue

    #     # 如果设置了question，直接使用这个question
    #     if next_flow.question is not None:
    #         content = SuggestContent(
    #             appId=next_flow_app_id,
    #             flowId=next_flow.id,
    #             flowDescription=str(flow_metadata.description),
    #             question=next_flow.question,
    #         )
    #         await queue.push_output(event_type=EventType.SUGGEST, data=content.model_dump(exclude_none=True, by_alias=True))
    #         continue

    #     # 没有设置question，则需要生成问题
    #     rewrite_question = await Recommend().generate(
    #         task_id=task_id,
    #         action_description=flow_metadata.description,
    #         history_questions=last_n_questions,
    #         recent_question=current_record,
    #         user_preference=str(user_domain),
    #         shown_questions=generated_questions,
    #     )
    #     generated_questions += f"{rewrite_question}\n"
    #     content = SuggestContent(
    #         appId=next_flow_app_id,
    #         flowId=next_flow.id,
    #         flowDescription=str(flow_metadata.description),
    #         question=rewrite_question,
    #     )
    #     await queue.push_output(event_type=EventType.SUGGEST, data=content.model_dump(exclude_none=True, by_alias=True))
    #     continue
    # return
