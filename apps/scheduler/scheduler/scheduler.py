# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调度器；负责任务的分发与执行"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.queue import MessageQueue
from apps.common.security import Security
from apps.llm import LLM, LLMConfig, embedding, json_generator
from apps.models import (
    AppType,
    Conversation,
    ExecutorStatus,
    Record,
    RecordMetadata,
    StepStatus,
    Task,
    TaskRuntime,
    User,
)
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.executor.qa import QAExecutor
from apps.scheduler.pool.pool import pool
from apps.schemas.enum_var import EventType
from apps.schemas.message import (
    InitContent,
    InitContentFeature,
)
from apps.schemas.record import FlowHistory, RecordContent
from apps.schemas.request_data import RequestData
from apps.schemas.scheduler import TopFlow
from apps.schemas.task import TaskData
from apps.services.activity import Activity
from apps.services.appcenter import AppCenterManager
from apps.services.conversation import ConversationManager
from apps.services.document import DocumentManager
from apps.services.llm import LLMManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

from .prompt import FLOW_SELECT

_logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    task: TaskData
    llm: LLMConfig
    queue: MessageQueue
    post_body: RequestData
    user: User


    async def init(
            self,
            task_id: uuid.UUID,
            queue: MessageQueue,
            post_body: RequestData,
            user_sub: str,
    ) -> None:
        """初始化"""
        self.queue = queue
        self.post_body = post_body
        # 获取用户
        user = await UserManager.get_user(user_sub)
        if not user:
            err = f"[Scheduler] 用户 {user_sub} 不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.user = user

        # 初始化Task
        await self._init_task(task_id, user_sub)

        # Jinja2
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )

        # LLM
        self.llm = await self._get_scheduler_llm(post_body.llm_id)


    async def _push_init_message(
        self, context_num: int, *, is_flow: bool = False,
    ) -> None:
        """推送初始化消息"""
        # 组装feature
        if is_flow:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=False,
                enableRegenerate=False,
            )
        else:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=True,
                enableRegenerate=True,
            )

        # 保存必要信息到Task
        created_at = round(datetime.now(UTC).timestamp(), 3)
        self.task.runtime.time = created_at

        # 推送初始化消息
        await self.queue.push_output(
            self.task,
            self.llm,
            event_type=EventType.INIT.value,
            data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
        )

    async def _push_done_message(self) -> None:
        """推送任务完成消息"""
        _logger.info("[Scheduler] 发送结束消息")
        await self.queue.push_output(self.task, self.llm, event_type=EventType.DONE.value, data={})

    async def _determine_app_id(self) -> uuid.UUID | None:
        """
        确定最终使用的 app_id

        Returns:
            final_app_id: 最终使用的 app_id，如果为 None 则使用 QA 模式

        """
        conversation = None

        if self.task.metadata.conversationId:
            conversation = await ConversationManager.get_conversation_by_conversation_id(
                self.task.metadata.userSub,
                self.task.metadata.conversationId,
            )

        if conversation and conversation.appId:
            # Conversation中有appId，使用它
            final_app_id = conversation.appId
            _logger.info("[Scheduler] 使用Conversation中的appId: %s", final_app_id)

            # 如果post_body中也有app_id且与Conversation不符，忽略post_body中的app信息
            if self.post_body.app and self.post_body.app.app_id and self.post_body.app.app_id != conversation.appId:
                _logger.warning(
                    "[Scheduler] post_body中的app_id(%s)与Conversation中的appId(%s)不符，忽略post_body中的app信息",
                    self.post_body.app.app_id,
                    conversation.appId,
                )
                # 清空post_body中的app信息，以Conversation为准
                self.post_body.app.app_id = conversation.appId
        elif self.post_body.app and self.post_body.app.app_id:
            # Conversation中appId为None，使用post_body中的app信息
            final_app_id = self.post_body.app.app_id
            _logger.info("[Scheduler] Conversation中无appId，使用post_body中的app_id: %s", final_app_id)
        else:
            # 两者都为None，fallback到QAExecutor
            final_app_id = None
            _logger.info("[Scheduler] Conversation和post_body中均无appId，fallback到智能问答")

        return final_app_id

    async def _create_executor_task(self, final_app_id: uuid.UUID | None) -> asyncio.Task | None:
        """
        根据 app_id 创建对应的执行器任务

        Args:
            final_app_id: 要使用的 app_id，None 表示使用 QA 模式

        Returns:
            创建的异步任务，如果发生错误则返回 None

        """
        if final_app_id is None:
            # 没有app相关信息，运行QAExecutor
            _logger.info("[Scheduler] 运行智能问答模式")
            await self._push_init_message(3, is_flow=False)
            return asyncio.create_task(self._run_qa())

        # 有app信息，获取app详情和元数据
        try:
            app_data = await AppCenterManager.fetch_app_metadata_by_id(final_app_id)
        except ValueError:
            _logger.exception("[Scheduler] App %s 不存在或元数据文件缺失", final_app_id)
            await self.queue.close()
            return None

        # 获取上下文窗口并根据app类型决定执行器
        context_num = app_data.history_len
        _logger.info("[Scheduler] App上下文窗口: %d", context_num)

        if app_data.app_type == AppType.FLOW:
            _logger.info("[Scheduler] 运行Flow应用")
            await self._push_init_message(context_num, is_flow=True)
            return asyncio.create_task(self._run_flow())

        _logger.info("[Scheduler] 运行MCP Agent应用")
        await self._push_init_message(context_num, is_flow=False)
        return asyncio.create_task(self._run_agent())

    async def _handle_task_cancellation(self, main_task: asyncio.Task) -> None:
        """
        处理任务取消的逻辑

        Args:
            main_task: 需要取消的主任务

        """
        _logger.warning("[Scheduler] 用户取消执行，正在终止...")
        main_task.cancel()
        try:
            await main_task
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 主任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 终止工作流时发生错误")

        # 检查ExecutorState，若为init、running或waiting，将状态改为cancelled
        if self.task.state and self.task.state.executorStatus in [
            ExecutorStatus.INIT,
            ExecutorStatus.RUNNING,
            ExecutorStatus.WAITING,
        ]:
            self.task.state.executorStatus = ExecutorStatus.CANCELLED
            _logger.info("[Scheduler] ExecutorStatus已设置为CANCELLED")
        elif self.task.state:
            _logger.info("[Scheduler] ExecutorStatus为 %s，保持不变", self.task.state.executorStatus)
        else:
            _logger.warning("[Scheduler] task.state为None，无法更新ExecutorStatus")

    async def _monitor_activity(self, kill_event: asyncio.Event, user_sub: str) -> None:
        """监控用户活动状态，不活跃时终止工作流"""
        try:
            check_interval = 0.5  # 每0.5秒检查一次

            while not kill_event.is_set():
                # 检查用户活动状态
                is_active = await Activity.is_active(user_sub)

                if not is_active:
                    _logger.warning("[Scheduler] 用户 %s 不活跃，终止工作流", user_sub)
                    kill_event.set()
                    break

                # 控制检查频率
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 活动监控任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 活动监控过程中发生错误")
            kill_event.set()


    async def _get_scheduler_llm(self, reasoning_llm_id: str) -> LLMConfig:
        """获取RAG大模型"""
        # 获取当前会话使用的大模型
        reasoning_llm = await LLMManager.get_llm(reasoning_llm_id)
        if not reasoning_llm:
            err = "[Scheduler] 获取问答用大模型ID失败"
            _logger.error(err)
            raise ValueError(err)
        reasoning_llm = LLM(reasoning_llm)

        # 获取功能性的大模型信息
        function_llm = None
        if not self.user.functionLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置函数调用大模型，相关功能将被禁用", self.user.userSub)
        else:
            function_llm = await LLMManager.get_llm(self.user.functionLLM)
            if not function_llm:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的函数调用大模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.functionLLM,
                )
            else:
                function_llm = LLM(function_llm)

        # 获取并设置全局embedding模型
        embedding_obj = None
        if not self.user.embeddingLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置向量模型，相关功能将被禁用", self.user.userSub)
        else:
            embedding_llm_config = await LLMManager.get_llm(self.user.embeddingLLM)
            if not embedding_llm_config:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的向量模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.embeddingLLM,
                )
            else:
                # 设置全局embedding配置
                await embedding.init(embedding_llm_config)
                embedding_obj = embedding

        return LLMConfig(
            reasoning=reasoning_llm,
            function=function_llm,
            embedding=embedding_obj,
        )


    async def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        if not self.llm.function:
            err = "[Scheduler] 未设置Function模型"
            _logger.error(err)
            raise RuntimeError(err)

        # 获取所选应用的所有Flow
        if not self.post_body.app or not self.post_body.app.app_id:
            err = "[Scheduler] 未选择应用"
            _logger.error(err)
            raise RuntimeError(err)

        flow_list = await pool.get_flow_metadata(self.post_body.app.app_id)
        if not flow_list:
            err = "[Scheduler] 未找到应用中合法的Flow"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[Scheduler] 选择应用 %s 最合适的Flow", self.post_body.app.app_id)
        choices = [{
            "name": flow.id,
            "description": f"{flow.name}, {flow.description}",
        } for flow in flow_list]

        # 根据用户语言选择模板
        template = self._env.from_string(FLOW_SELECT[self.task.runtime.language])
        # 渲染模板
        prompt = template.render(
            template,
            question=self.post_body.question,
            choice_list=choices,
        )
        schema = TopFlow.model_json_schema()
        schema["properties"]["choice"]["enum"] = [choice["name"] for choice in choices]
        function = {
            "name": "select_flow",
            "description": "Select the appropriate flow",
            "parameters": schema,
        }
        result_str = await json_generator.generate(
            query=self.post_body.question,
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        result = TopFlow.model_validate(result_str)
        return result.choice


    async def create_new_conversation(
        self, title: str, user_sub: str, app_id: uuid.UUID | None = None,
        *,
        debug: bool = False,
    ) -> Conversation:
        """判断并创建新对话"""
        # 新建对话
        if app_id and not await AppCenterManager.validate_user_app_access(user_sub, app_id):
            err = "Invalid app_id."
            raise RuntimeError(err)
        new_conv = await ConversationManager.add_conversation_by_user_sub(
            title=title,
            user_sub=user_sub,
            app_id=app_id,
            debug=debug,
        )
        if not new_conv:
            err = "Create new conversation failed."
            raise RuntimeError(err)
        return new_conv


    def _create_new_task(self, task_id: uuid.UUID, user_sub: str, conversation_id: uuid.UUID | None) -> TaskData:
        """创建新的TaskData"""
        return TaskData(
            metadata=Task(
                id=task_id,
                userSub=user_sub,
                conversationId=conversation_id,
            ),
            runtime=TaskRuntime(
                taskId=task_id,
            ),
            state=None,
            context=[],
        )

    async def _init_task(self, task_id: uuid.UUID, user_sub: str) -> None:
        """初始化Task"""
        conversation_id = self.post_body.conversation_id

        # 若没有Conversation ID则直接创建task
        if not conversation_id:
            _logger.info("[Scheduler] 无Conversation ID，直接创建新任务")
            self.task = self._create_new_task(task_id, user_sub, None)
            return

        # 有ConversationID则尝试从ConversationID中恢复task
        _logger.info("[Scheduler] 尝试从Conversation ID %s 恢复任务", conversation_id)

        # 尝试恢复任务
        restored = False
        try:
            # 先验证conversation是否存在且属于该用户
            conversation = await ConversationManager.get_conversation_by_conversation_id(
                user_sub,
                conversation_id,
            )

            if conversation:
                # 尝试从Conversation中获取最后一个Task
                last_task = await TaskManager.get_task_by_conversation_id(conversation_id, user_sub)

                # 如果能获取到task，则加载完整的TaskData
                if last_task and last_task.id:
                    _logger.info("[Scheduler] 从Conversation恢复任务 %s", last_task.id)
                    task_data = await TaskManager.get_task_data_by_task_id(last_task.id)
                    if task_data:
                        self.task = task_data
                        # 更新task_id为新的task_id
                        self.task.metadata.id = task_id
                        self.task.runtime.taskId = task_id
                        if self.task.state:
                            self.task.state.taskId = task_id
                        restored = True
            else:
                _logger.warning(
                    "[Scheduler] Conversation %s 不存在或无权访问，创建新任务",
                    conversation_id,
                )
        except Exception:
            _logger.exception("[Scheduler] 从Conversation恢复任务失败，创建新任务")

        # 恢复不成功则新建task
        if not restored:
            _logger.info("[Scheduler] 无法恢复任务，创建新任务")
            self.task = self._create_new_task(task_id, user_sub, conversation_id)


    async def run(self) -> None:
        """运行调度器"""
        _logger.info("[Scheduler] 开始执行")

        # 创建用于通信的事件和监控任务
        kill_event = asyncio.Event()
        monitor = asyncio.create_task(self._monitor_activity(kill_event, self.task.metadata.userSub))

        # 确定最终使用的 app_id
        final_app_id = await self._determine_app_id()

        # 根据 app_id 创建对应的执行器任务
        main_task = await self._create_executor_task(final_app_id)
        if main_task is None:
            # 创建任务失败（通常是因为 app 不存在），直接返回
            return

        # 等待任一任务完成
        done, pending = await asyncio.wait(
            [main_task, monitor],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 如果用户手动终止，则取消主任务
        if kill_event.is_set():
            await self._handle_task_cancellation(main_task)

        # 更新Task，发送结束消息
        await self._push_done_message()
        # 关闭Queue
        await self.queue.close()


    async def _run_qa(self) -> None:
        qa_executor = QAExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            llm=self.llm,
        )
        _logger.info("[Scheduler] 开始智能问答")
        await qa_executor.init()
        await qa_executor.run()
        self.task = qa_executor.task


    async def _run_flow(self) -> None:
        # 获取应用信息
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择应用")
            return

        _logger.info("[Scheduler] 获取工作流元数据")
        flow_info = await pool.get_flow_metadata(self.post_body.app.app_id)

        # 如果flow_info为空，则直接返回
        if not flow_info:
            _logger.error("[Scheduler] 未找到工作流元数据")
            return

        # 如果用户选了特定的Flow
        if not self.post_body.app.flow_id:
            _logger.info("[Scheduler] 选择最合适的流")
            flow_id = await self.get_top_flow()
        else:
            # 如果用户没有选特定的Flow，则根据语义选择一个Flow
            flow_id = self.post_body.app.flow_id
        _logger.info("[Scheduler] 获取工作流定义")
        flow_data = await pool.get_flow(self.post_body.app.app_id, flow_id)

        # 如果flow_data为空，则直接返回
        if not flow_data:
            _logger.error("[Scheduler] 未找到工作流定义")
            return

        # 初始化Executor
        flow_exec = FlowExecutor(
            flow_id=flow_id,
            flow=flow_data,
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            post_body_app=self.post_body.app,
            llm=self.llm,
        )

        # 开始运行
        _logger.info("[Scheduler] 运行工作流执行器")
        await flow_exec.init()
        await flow_exec.run()
        self.task = flow_exec.task


    async def _run_agent(self) -> None:
        """构造Executor并执行"""
        # 获取应用信息
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择MCP应用")
            return

        # 初始化Executor
        agent_exec = MCPAgentExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            agent_id=self.post_body.app.app_id,
            params=self.post_body.app.params,
            llm=self.llm,
        )
        # 开始运行
        _logger.info("[Scheduler] 运行MCP执行器")
        await agent_exec.init()
        await agent_exec.run()
        self.task = agent_exec.task


    async def _save_data(self) -> None:
        """保存当前Executor、Task、Record等的数据"""
        task = self.task
        user_sub = self.task.metadata.userSub
        post_body = self.post_body

        # 构造文档列表
        used_docs = []
        record_group = None  # TODO: 需要从适当的地方获取record_group

        # 处理文档
        if hasattr(task.runtime, "documents") and task.runtime.documents:
            for docs in task.runtime.documents:
                doc_dict = docs if isinstance(docs, dict) else (docs.model_dump() if hasattr(docs, "model_dump") else docs)
                used_docs.append(doc_dict)

        # 组装RecordContent
        record_content = RecordContent(
            question=task.runtime.question if hasattr(task.runtime, "question") else "",
            answer=task.runtime.answer if hasattr(task.runtime, "answer") else "",
            facts=task.runtime.facts if hasattr(task.runtime, "facts") else [],
            data={},
        )

        try:
            # 加密Record数据
            encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
        except Exception:
            _logger.exception("[Scheduler] 问答对加密错误")
            return

        # 保存Flow信息
        if task.state:
            # 遍历查找数据，并添加
            await TaskManager.save_flow_context(task.context)

        # 整理Record数据
        current_time = round(datetime.now(UTC).timestamp(), 2)
        record = Record(
            id=task.metadata.id,  # record_id
            conversationId=task.metadata.conversationId,
            taskId=task.metadata.id,
            userSub=user_sub,
            content=encrypt_data,
            key=encrypt_config,
            metadata=RecordMetadata(
                timeCost=0,  # TODO: 需要从task中获取时间成本
                inputTokens=0,  # TODO: 需要从task中获取token信息
                outputTokens=0,  # TODO: 需要从task中获取token信息
                feature={},
            ),
            createdAt=current_time,
            flow=FlowHistory(
                flow_id=task.state.flow_id if task.state else "",
                flow_name=task.state.flow_name if task.state else "",
                flow_status=task.state.flow_status if task.state else StepStatus.SUCCESS,
                history_ids=[context.id for context in task.context],
            ) if task.state else None,
        )

        # 修改文件状态
        if record_group and post_body.conversation_id:
            await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)

        # 保存Record
        if post_body.conversation_id:
            await RecordManager.insert_record_data(user_sub, post_body.conversation_id, record)

        # 保存与答案关联的文件
        if record_group and used_docs:
            await DocumentManager.save_answer_doc(user_sub, record_group, used_docs)

        if post_body.app and post_body.app.app_id:
            # 更新最近使用的应用
            await AppCenterManager.update_recent_app(user_sub, post_body.app.app_id)

        # 若状态为成功，删除Task
        if not task.state or task.state.flow_status in [StepStatus.SUCCESS, StepStatus.ERROR, StepStatus.CANCELLED]:
            await TaskManager.delete_task_by_task_id(task.metadata.id)
        else:
            # 更新Task
            await TaskManager.save_task(task.metadata.id, task.metadata)
            await TaskManager.save_task_runtime(task.runtime)
            if task.state:
                await TaskManager.save_executor_checkpoint(task.state)
