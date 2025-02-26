"""Scheduler模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import traceback

import ray

from apps.constants import LOGGER
from apps.entities.enum_var import EventType
from apps.entities.rag_data import RAGQueryReq
from apps.entities.request_data import RequestData
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import SchedulerResult, TaskBlock
from apps.manager.appcenter import AppCenterManager
from apps.manager.user import UserManager
from apps.scheduler.executor.flow import Executor
from apps.scheduler.scheduler.context import get_context, get_docs
from apps.scheduler.scheduler.flow import FlowChooser
from apps.scheduler.scheduler.message import (
    push_document_message,
    push_init_message,
    push_rag_message,
)


@ray.remote
class Scheduler:
    """“调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    async def run(self, task_id: str, queue: ray.ObjectRef, user_sub: str, post_body: RequestData) -> SchedulerResult:
        """运行调度器"""
        task_actor = ray.get_actor("task")
        try:
            task = await task_actor.get_task.remote(task_id)
        except Exception as e:
            LOGGER.error(f"[Scheduler] Task {task_id} not found: {e!s}\n{traceback.format_exc()}")
            await queue.close.remote() # type: ignore[attr-defined]
            return SchedulerResult(used_docs=[])

        try:
            # 获取当前问答可供关联的文档
            docs, doc_ids = await get_docs(user_sub, post_body)
        except Exception as e:
            LOGGER.error(f"[Scheduler] Get docs failed: {e!s}\n{traceback.format_exc()}")
            await queue.close.remote() # type: ignore[attr-defined]
            return SchedulerResult(used_docs=[])

        # 获取用户配置的kb_sn
        user_info = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_info:
            err = "[Scheduler] User not found"
            LOGGER.error(err)
            await queue.close.remote() # type: ignore[attr-defined]
            return SchedulerResult(used_docs=[])

        # 组装RAG请求数据，备用
        rag_data = RAGQueryReq(
            question=post_body.question,
            language=post_body.language,
            document_ids=doc_ids,
            kb_sn=None if not user_info.kb_id else user_info.kb_id,
            top_k=5,
        )
        # 已使用文档
        used_docs = []

        # 如果是智能问答，直接执行
        if not post_body.app or post_body.app.app_id == "":
            await push_init_message(task_id, queue, 3, is_flow=False)
            await asyncio.sleep(0.1)
            for doc in docs:
                # 保存使用的文件ID
                used_docs.append(doc.id)
                await push_document_message(task_id, queue, doc)
                await asyncio.sleep(0.1)

            # 保存有数据的最后一条消息
            await push_rag_message(task_id, queue, user_sub, rag_data)
        else:
            # 查找对应的App元数据
            app_data = await AppCenterManager.fetch_app_data_by_id(post_body.app.app_id)
            if not app_data:
                LOGGER.error(f"[Scheduler] App {post_body.app.app_id} not found")
                await queue.close.remote() # type: ignore[attr-defined]
                return SchedulerResult(used_docs=[])

            # 获取上下文
            context, facts = await get_context(user_sub, post_body, app_data.history_len)

            # 需要执行Flow
            await push_init_message(task_id, queue, app_data.history_len, is_flow=True)
            # 组装上下文
            executor_background = ExecutorBackground(
                conversation=context,
                facts=facts,
            )
            await self.run_executor(task, queue, post_body, executor_background)

        # 发送结束消息
        task = await task_actor.get_task.remote(task_id)
        await queue.push_output.remote(task, event_type=EventType.DONE, data={}) # type: ignore[attr-defined]
        # 关闭Queue
        await queue.close.remote() # type: ignore[attr-defined]

        return SchedulerResult(used_docs=used_docs)


    async def run_executor(self, task: TaskBlock, queue: ray.ObjectRef, post_body: RequestData, background: ExecutorBackground) -> None:
        """构造FlowExecutor，并执行所选择的流"""
        # 读取App中所有Flow的信息
        LOGGER.info(f"[Scheduler] Getting flow metadata for app {post_body.app}...")
        pool_actor = ray.get_actor("pool")
        if not post_body.app:
            LOGGER.error("[Scheduler] Not using workflow!")
            return
        LOGGER.info(f"[Scheduler] Getting flow metadata for app {post_body.app}...")
        flow_info = await pool_actor.get_flow_metadata.remote(post_body.app.app_id)

        # 如果flow_info为空，则直接返回
        if not flow_info:
            LOGGER.error(f"[Scheduler] Flow info not found for app {post_body.app.app_id}")
            return

        # 如果用户选了特定的Flow
        if post_body.app.flow_id:
            LOGGER.info(f"[Scheduler] Getting flow data for app {post_body.app.app_id} and flow {post_body.app.flow_id}...")
            flow_data = await pool_actor.get_flow.remote(post_body.app.app_id, post_body.app.flow_id)
        else:
            # 如果用户没有选特定的Flow，则根据语义选择一个Flow
            LOGGER.info(f"[Scheduler] Choosing top flow for app {post_body.app.app_id}...")
            flow_chooser = FlowChooser(task.record.task_id, post_body.question, post_body.app)
            flow_id = await flow_chooser.get_top_flow()
            LOGGER.info(f"[Scheduler] Getting flow data for app {post_body.app.app_id} and flow {flow_id}...")
            flow_data = await pool_actor.get_flow.remote(post_body.app.app_id, flow_id)

        # 如果flow_data为空，则直接返回
        if not flow_data:
            LOGGER.error(f"[Scheduler] Flow data not found for app {post_body.app.app_id} and flow {flow_id}")
            return

        # 初始化Executor
        LOGGER.info(f"[Scheduler] Initializing executor for app {post_body.app.app_id} and flow {flow_id}...")
        flow_exec = Executor(
            name=flow_data.name,
            description=flow_data.description,
            flow=flow_data,
            task=task,
            queue=queue,
            question=post_body.question,
            post_body_app=post_body.app,
            executor_background=background,
        )
        # 开始运行
        LOGGER.info(f"[Scheduler] Loading state for app {post_body.app.app_id} and flow {flow_id}...")
        await flow_exec.load_state()
        LOGGER.info(f"[Scheduler] Running executor for app {post_body.app.app_id} and flow {flow_id}...")
        await flow_exec.run()
