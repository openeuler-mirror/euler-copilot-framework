"""Scheduler模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import traceback
from datetime import datetime, timezone
from typing import Union

from apps.common.queue import MessageQueue
from apps.common.security import Security
from apps.constants import LOGGER
from apps.entities.collection import (
    Document,
    Record,
)
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.plugin import ExecutorBackground, SysExecVars
from apps.entities.rag_data import RAGQueryReq
from apps.entities.record import RecordDocument
from apps.entities.request_data import RequestData
from apps.entities.task import RequestDataApp
from apps.manager import (
    DocumentManager,
    RecordManager,
    TaskManager,
    UserManager,
)
# from apps.scheduler.executor import Executor
from apps.scheduler.scheduler.context import generate_facts, get_context
# from apps.scheduler.scheduler.flow import choose_flow
from apps.scheduler.scheduler.message import (
    push_document_message,
    push_init_message,
    push_rag_message,
)
from apps.service.suggestion import plan_next_flow


class Scheduler:
    """“调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    def __init__(self, task_id: str, queue: MessageQueue) -> None:
        """初始化Scheduler"""
        self._task_id = task_id
        self._queue = queue
        self.used_docs = []


    async def _get_docs(self, user_sub: str, post_body: RequestData) -> tuple[Union[list[RecordDocument], list[Document]], list[str]]:
        """获取当前问答可供关联的文档"""
        doc_ids = []
        if post_body.group_id:
            # 是重新生成，直接从RecordGroup中获取
            docs = await DocumentManager.get_used_docs_by_record_group(user_sub, post_body.group_id)
            doc_ids += [doc.id for doc in docs]
        else:
            # 是新提问
            # 从Conversation中获取刚上传的文档
            docs = await DocumentManager.get_unused_docs(user_sub, post_body.conversation_id)
            # 从最近10条Record中获取文档
            docs += await DocumentManager.get_used_docs(user_sub, post_body.conversation_id, 10)
            doc_ids += [doc.id for doc in docs]

        return docs, doc_ids


    async def run(self, user_sub: str, session_id: str, post_body: RequestData) -> None:
        """运行调度器"""
        # 捕获所有异常：出现问题就输出日志，并停止queue
        try:
            # 根据用户的请求，返回插件ID列表，选择Flow
            # self._plugin_id, user_selected_flow = await choose_flow(self._task_id, post_body.question, post_body.apps)
            user_selected_flow = None
            # 获取当前问答可供关联的文档
            docs, doc_ids = await self._get_docs(user_sub, post_body)
            # 获取上下文；最多20轮
            context, facts = await get_context(user_sub, post_body, post_body.features.context_num)

            # 获取用户配置的kb_sn
            user_info = await UserManager.get_userinfo_by_user_sub(user_sub)
            if not user_info:
                err = "[Scheduler] User not found"
                raise ValueError(err)  # noqa: TRY301
            # 组装RAG请求数据，备用
            rag_data = RAGQueryReq(
                question=post_body.question,
                language=post_body.language,
                document_ids=doc_ids,
                kb_sn=None if user_info is None or not user_info.kb_id else user_info.kb_id,
                history=context,
                top_k=5,
            )

            # 状态位：是否需要生成推荐问题？
            need_recommend = True
            # 如果是智能问答，直接执行
            if not user_selected_flow:
                # await push_init_message(self._task_id, self._queue, post_body, is_flow=False)
                await asyncio.sleep(0.1)
                for doc in docs:
                    # 保存使用的文件ID
                    self.used_docs.append(doc.id)
                    await push_document_message(self._queue, doc)

                # 保存有数据的最后一条消息
                await push_rag_message(self._task_id, self._queue, user_sub, rag_data)
            else:
                # 需要执行Flow
                # await push_init_message(self._task_id, self._queue, post_body, is_flow=True)
                # 组装上下文
                background = ExecutorBackground(
                    conversation=context,
                    facts=facts,
                )
                need_recommend = await self.run_executor(session_id, post_body, background, user_selected_flow)

            # 生成推荐问题和事实提取
            # 如果需要生成推荐问题，则生成
            if need_recommend:
                routine_results = await asyncio.gather(
                    # generate_facts(self._task_id, post_body.question),
                    plan_next_flow(user_sub, self._task_id, self._queue, post_body.app),
                )
            # else:
                # routine_results = await asyncio.gather(generate_facts(self._task_id, post_body.question))

            # 保存事实信息
            self._facts = routine_results[0]

            # 发送结束消息
            await self._queue.push_output(event_type=EventType.DONE, data={})
            # 关闭Queue
            await self._queue.close()
        except Exception as e:
            LOGGER.error(f"[Scheduler] Error: {e!s}\n{traceback.format_exc()}")
            await self._queue.close()


    async def run_executor(self, session_id: str, post_body: RequestData, background: ExecutorBackground, user_selected_flow: RequestDataApp) -> bool:
        """构造FlowExecutor，并执行所选择的流"""
        # 获取当前Task
        task = await TaskManager.get_task(self._task_id)
        if not task:
            err = "[Scheduler] Task error."
            raise ValueError(err)

        # 设置Flow接受的系统变量
        param = SysExecVars(
            queue=self._queue,
            question=post_body.question,
            task_id=self._task_id,
            session_id=session_id,
            app_data=user_selected_flow,
            background=background,
        )

        # 执行Executor
        # flow_exec = Executor()
        # await flow_exec.load_state(param)
        # # 开始运行
        # await flow_exec.run()
        # # 判断状态
        # return flow_exec.flow_state.status != StepStatus.PARAM

    async def save_state(self, user_sub: str, post_body: RequestData) -> None:
        """保存当前Executor、Task、Record等的数据"""
        # 获取当前Task
        task = await TaskManager.get_task(self._task_id)
        if not task:
            err = "Task not found"
            raise ValueError(err)

        # 加密Record数据
        try:
            encrypt_data, encrypt_config = Security.encrypt(task.record.content.model_dump_json(by_alias=True))
        except Exception as e:
            LOGGER.info(f"[Scheduler] Encryption failed: {e}")
            return

        # 保存Flow信息
        if task.flow_state:
            # 循环创建FlowHistory
            history_data = []
            # 遍历查找数据，并添加
            for history_id in task.new_context:
                for history in task.flow_context.values():
                    if history.id == history_id:
                        history_data.append(history)
                        break
            await TaskManager.create_flows(history_data)

        # 修改metadata里面时间为实际运行时间
        task.record.metadata.time = round(datetime.now(timezone.utc).timestamp() - task.record.metadata.time, 2)

        # 整理Record数据
        record = Record(
            record_id=task.record.id,
            user_sub=user_sub,
            data=encrypt_data,
            key=encrypt_config,
            # facts=self._facts,
            #TODO:暂时不使用facts
            facts=[],
            metadata=task.record.metadata,
            created_at=task.record.created_at,
            flow=task.new_context,
        )

        record_group = task.record.group_id
        # 检查是否存在group_id
        if not await RecordManager.check_group_id(record_group, user_sub):
            record_group = await RecordManager.create_record_group(user_sub, post_body.conversation_id, self._task_id)
            if not record_group:
                LOGGER.error("[Scheduler] Create record group failed.")
                return

        # 修改文件状态
        await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)
        # 保存Record
        await RecordManager.insert_record_data_into_record_group(user_sub, record_group, record)
        # 保存与答案关联的文件
        await DocumentManager.save_answer_doc(user_sub, record_group, self.used_docs)
