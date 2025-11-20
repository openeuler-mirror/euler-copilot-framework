# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""初始化相关的Mixin类"""

import logging
import uuid
from datetime import UTC, datetime

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.queue import MessageQueue
from apps.llm import LLM
from apps.models import Conversation, Task, TaskRuntime, User
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.appcenter import AppCenterManager
from apps.services.conversation import ConversationManager
from apps.services.llm import LLMManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)


class InitMixin:
    """处理Scheduler初始化相关的逻辑"""

    task: TaskData
    user: User
    post_body: RequestData
    queue: MessageQueue
    llm: LLM
    _env: SandboxedEnvironment

    async def _get_scheduler_llm(self, reasoning_llm_id: str) -> LLM:
        """获取RAG大模型"""
        reasoning_llm = await LLMManager.get_llm(reasoning_llm_id)
        if not reasoning_llm:
            err = "[Scheduler] 获取问答用大模型ID失败"
            _logger.error(err)
            raise ValueError(err)
        return LLM(reasoning_llm)

    def _create_new_task(self, user_id: str, conversation_id: uuid.UUID | None, auth_header: str) -> None:
        """创建新的TaskData"""
        task_id = uuid.uuid4()
        self.task = TaskData(
            metadata=Task(
                id=task_id,
                userId=user_id,
                conversationId=conversation_id,
                updatedAt=datetime.now(UTC),
            ),
            runtime=TaskRuntime(
                taskId=task_id,
                authHeader=auth_header,
                userInput=self.post_body.question,
                language=self.post_body.language,
            ),
            state=None,
            context=[],
        )

    async def _init_task(self, user_id: str, auth_header: str) -> None:
        """初始化Task"""
        conversation_id = self.post_body.conversation_id

        if not conversation_id:
            _logger.info("[Scheduler] 无Conversation ID，直接创建新任务")
            self._create_new_task(user_id, None, auth_header)
            return

        _logger.info("[Scheduler] 尝试从Conversation ID %s 恢复任务", conversation_id)

        try:
            conversation = await ConversationManager.get_conversation_by_conversation_id(
                user_id,
                conversation_id,
            )

            if conversation:
                last_task = await TaskManager.get_task_by_conversation_id(conversation_id, user_id)

                if last_task and last_task.id:
                    _logger.info("[Scheduler] 从Conversation恢复任务 %s", last_task.id)
                    task_data = await TaskManager.get_task_data_by_task_id(last_task.id)
                    if task_data:
                        self.task = task_data
                        # 恢复任务时保留原有的 task_id，但更新 authHeader
                        self.task.runtime.authHeader = auth_header
                        return
            else:
                _logger.warning(
                    "[Scheduler] Conversation %s 不存在或无权访问，创建新任务",
                    conversation_id,
                )
        except Exception:
            _logger.exception("[Scheduler] 从Conversation恢复任务失败，创建新任务")

        _logger.info("[Scheduler] 无法恢复任务，创建新任务")
        self._create_new_task(user_id, conversation_id, auth_header)

    async def _get_user(self, user_id: str) -> None:
        """初始化用户"""
        user = await UserManager.get_user(user_id)
        if not user:
            err = f"[Scheduler] 用户 {user_id} 不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.user = user

    def _init_jinja2_env(self) -> None:
        """初始化Jinja2环境"""
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )

    async def _create_new_conversation(
        self, title: str, user_id: str, app_id: uuid.UUID | None = None,
        *,
        debug: bool = False,
    ) -> Conversation:
        """判断并创建新对话，并将conversation ID写入task"""
        if app_id and not await AppCenterManager.validate_user_app_access(user_id, app_id):
            err = "Invalid app_id."
            raise RuntimeError(err)
        new_conv = await ConversationManager.add_conversation_by_user(
            title=title,
            user_id=user_id,
            app_id=app_id,
            debug=debug,
        )
        if not new_conv:
            err = "Create new conversation failed."
            raise RuntimeError(err)

        # 将conversation ID写入task
        self.task.metadata.conversationId = new_conv.id
        _logger.info("[Scheduler] Conversation ID已写入Task: %s", new_conv.id)

        return new_conv
