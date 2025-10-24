# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""初始化相关的Mixin类"""

import logging
import uuid

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.queue import MessageQueue
from apps.llm import LLM, LLMConfig, embedding
from apps.models import Task, TaskRuntime, User
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.conversation import ConversationManager
from apps.services.llm import LLMManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)


class InitializationMixin:
    """处理Scheduler初始化相关的逻辑"""

    task: TaskData
    user: User
    post_body: RequestData
    queue: MessageQueue
    llm: LLMConfig
    _env: SandboxedEnvironment

    async def _get_scheduler_llm(self, reasoning_llm_id: str) -> LLMConfig:
        """获取RAG大模型"""
        reasoning_llm = await LLMManager.get_llm(reasoning_llm_id)
        if not reasoning_llm:
            err = "[Scheduler] 获取问答用大模型ID失败"
            _logger.error(err)
            raise ValueError(err)
        reasoning_llm = LLM(reasoning_llm)

        function_llm = None
        if not self.user.functionLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置函数调用大模型，相关功能将被禁用", self.user.id)
        else:
            function_llm = await LLMManager.get_llm(self.user.functionLLM)
            if not function_llm:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的函数调用大模型ID %s 不存在，相关功能将被禁用",
                    self.user.id, self.user.functionLLM,
                )
            else:
                function_llm = LLM(function_llm)

        embedding_obj = None
        if not self.user.embeddingLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置向量模型，相关功能将被禁用", self.user.id)
        else:
            embedding_llm_config = await LLMManager.get_llm(self.user.embeddingLLM)
            if not embedding_llm_config:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的向量模型ID %s 不存在，相关功能将被禁用",
                    self.user.id, self.user.embeddingLLM,
                )
            else:
                await embedding.init(embedding_llm_config)
                embedding_obj = embedding

        return LLMConfig(
            reasoning=reasoning_llm,
            function=function_llm,
            embedding=embedding_obj,
        )

    def _create_new_task(self, task_id: uuid.UUID, user_id: str, conversation_id: uuid.UUID | None) -> TaskData:
        """创建新的TaskData"""
        return TaskData(
            metadata=Task(
                id=task_id,
                userId=user_id,
                conversationId=conversation_id,
            ),
            runtime=TaskRuntime(
                taskId=task_id,
            ),
            state=None,
            context=[],
        )

    async def _init_task(self, task_id: uuid.UUID, user_id: str) -> None:
        """初始化Task"""
        conversation_id = self.post_body.conversation_id

        if not conversation_id:
            _logger.info("[Scheduler] 无Conversation ID，直接创建新任务")
            self.task = self._create_new_task(task_id, user_id, None)
            return

        _logger.info("[Scheduler] 尝试从Conversation ID %s 恢复任务", conversation_id)

        restored = False
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

        if not restored:
            _logger.info("[Scheduler] 无法恢复任务，创建新任务")
            self.task = self._create_new_task(task_id, user_id, conversation_id)

    async def _init_user(self, user_id: str) -> None:
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
