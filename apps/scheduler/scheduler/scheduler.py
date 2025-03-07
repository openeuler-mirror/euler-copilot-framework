"""Scheduler模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import logging

import ray
from ray import actor

from apps.entities.enum_var import EventType, StepStatus
from apps.entities.rag_data import RAGQueryReq
from apps.entities.request_data import RequestData
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import SchedulerResult, TaskBlock
from apps.manager.appcenter import AppCenterManager
from apps.manager.flow import FlowManager
from apps.manager.user import UserManager
from apps.scheduler.executor.flow import Executor
from apps.scheduler.scheduler.context import get_context, get_docs
from apps.scheduler.scheduler.flow import FlowChooser
from apps.scheduler.scheduler.message import (
    push_document_message,
    push_init_message,
    push_rag_message,
)

logger = logging.getLogger("ray")


@ray.remote
class Scheduler:
    """“调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    async def run(self, task_id: str, queue: actor.ActorHandle, user_sub: str, post_body: RequestData) -> SchedulerResult:
        """运行调度器"""
        task_actor = ray.get_actor("task")
        try:
            task: TaskBlock = await task_actor.get_task.remote(task_id)
        except Exception:
            logger.exception("[Scheduler] 任务 %s 不存在", task_id)
            await queue.close.remote() # type: ignore[attr-defined]
            return SchedulerResult(used_docs=[])

        try:
            # 获取当前问答可供关联的文档
            docs, doc_ids = await get_docs(user_sub, post_body)
        except Exception:
            logger.exception("[Scheduler] 获取文档失败")
            await queue.close.remote() # type: ignore[attr-defined]
            return SchedulerResult(used_docs=[])

        # 获取用户配置的kb_sn
        user_info = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_info:
            logger.error("[Scheduler] 未找到用户")
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
            task = await push_init_message(task, queue, 3, is_flow=False)
            await asyncio.sleep(0.1)
            for doc in docs:
                # 保存使用的文件ID
                used_docs.append(doc.id)
                task = await push_document_message(task, queue, doc)
                await asyncio.sleep(0.1)

            # 保存有数据的最后一条消息
            task = await push_rag_message(task, queue, user_sub, rag_data)
        else:
            # 查找对应的App元数据
            app_data = await AppCenterManager.fetch_app_data_by_id(post_body.app.app_id)
            if not app_data:
                logger.error("[Scheduler] App %s 不存在", post_body.app.app_id)
                await queue.close.remote() # type: ignore[attr-defined]
                return SchedulerResult(used_docs=[])

            # 获取上下文
            context, facts = await get_context(user_sub, post_body, app_data.history_len)

            # 需要执行Flow
            task = await push_init_message(task, queue, app_data.history_len, is_flow=True)
            # 组装上下文
            executor_background = ExecutorBackground(
                conversation=context,
                facts=facts,
            )
            await self.run_executor(task, queue, post_body, executor_background)

        # 更新Task，发送结束消息
        task = await task_actor.set_task.remote(task_id, task)
        await queue.push_output.remote(task, event_type=EventType.DONE, data={}) # type: ignore[attr-defined]
        # 关闭Queue
        await queue.close.remote() # type: ignore[attr-defined]

        return SchedulerResult(used_docs=used_docs)


    async def run_executor(self, task: TaskBlock, queue: actor.ActorHandle, post_body: RequestData, background: ExecutorBackground) -> None:
        """构造FlowExecutor，并执行所选择的流"""
        # 读取App中所有Flow的信息
        pool_actor = ray.get_actor("pool")
        if not post_body.app:
            logger.error("[Scheduler] 未使用工作流功能！")
            return
        logger.info("[Scheduler] 获取工作流元数据")
        flow_info = await pool_actor.get_flow_metadata.remote(post_body.app.app_id)

        # 如果flow_info为空，则直接返回
        if not flow_info:
            logger.error("[Scheduler] 未找到工作流元数据")
            return

        # 如果用户选了特定的Flow
        if post_body.app.flow_id:
            logger.info("[Scheduler] 获取工作流定义")
            flow_id = post_body.app.flow_id
            flow_data = await pool_actor.get_flow.remote(post_body.app.app_id, flow_id)
        else:
            # 如果用户没有选特定的Flow，则根据语义选择一个Flow
            logger.info("[Scheduler] 选择最合适的流")
            flow_chooser = FlowChooser(task.record.task_id, post_body.question, post_body.app)
            flow_id = await flow_chooser.get_top_flow()
            logger.info("[Scheduler] 获取工作流定义")
            flow_data = await pool_actor.get_flow.remote(post_body.app.app_id, flow_id)

        # 如果flow_data为空，则直接返回
        if not flow_data:
            logger.error("[Scheduler] 未找到工作流定义")
            return

        # 初始化Executor
        logger.info("[Scheduler] 初始化Executor")

        flow_exec = Executor(
            flow_id=flow_id,
            flow=flow_data,
            task=task,
            queue=queue,
            question=post_body.question,
            post_body_app=post_body.app,
            executor_background=background,
        )

        # 开始运行
        logger.info("[Scheduler] 运行Executor")
        await flow_exec.load_state()
        await flow_exec.run()

        # 更新Task
        task_actor = ray.get_actor("task")
        task = await task_actor.get_task.remote(task.record.task_id)
        # 如果状态正常，则更新Flow的debug状态
        if task.flow_state and task.flow_state.status == StepStatus.SUCCESS:
            await FlowManager.update_flow_debug_by_app_and_flow_id(post_body.app.app_id, flow_id, debug=True)
        return
