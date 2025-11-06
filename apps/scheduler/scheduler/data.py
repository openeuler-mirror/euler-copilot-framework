# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""数据管理相关的Mixin类"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.common.security import Security
from apps.models import Conversation, ExecutorStatus, Record, RecordMetadata
from apps.schemas.record import RecordContent
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.appcenter import AppCenterManager
from apps.services.document import DocumentManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

_logger = logging.getLogger(__name__)

# 对话标题最大长度
_CONVERSATION_TITLE_MAX_LENGTH = 30


class DataMixin:
    """处理数据保存和管理相关的逻辑"""

    task: TaskData
    post_body: RequestData

    def _extract_used_documents(self) -> list[dict]:
        """提取任务运行时使用的文档列表"""
        used_docs = []
        task = self.task

        for docs in task.runtime.document:
            doc_dict = docs if isinstance(docs, dict) else (docs.model_dump() if hasattr(docs, "model_dump") else docs)
            used_docs.append(doc_dict)

        return used_docs

    def _build_record_content(self) -> RecordContent:
        """构建记录内容对象"""
        task = self.task

        return RecordContent(
            question=task.runtime.userInput,
            answer=task.runtime.fullAnswer,
            facts=task.runtime.fact,
            data={},
        )

    def _build_record(self, encrypt_data: str, encrypt_config: dict[str, Any], current_time: float) -> Record:
        """构建记录对象"""
        task = self.task
        user_id = task.metadata.userId

        return Record(
            id=task.metadata.id,
            conversationId=task.metadata.conversationId,
            taskId=task.metadata.id,
            userId=user_id,
            content=encrypt_data,
            key=encrypt_config,
            metadata=RecordMetadata(
                timeCost=0,
                inputTokens=0,
                outputTokens=0,
                feature={},
            ),
            createdAt=current_time,
        )

    async def _handle_document_management(self, record_group: str | None, used_docs: list[dict]) -> None:
        """处理文档管理相关操作"""
        user_id = self.task.metadata.userId
        post_body = self.post_body

        if record_group and post_body.conversation_id:
            await DocumentManager.change_doc_status(user_id, post_body.conversation_id, record_group)

        if record_group and used_docs:
            await DocumentManager.save_answer_doc(user_id, record_group, used_docs)

    async def _save_record_data(self, record_content: RecordContent, current_time: float) -> None:
        """加密并保存记录数据"""
        # 加密记录内容
        try:
            encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
        except Exception:
            _logger.exception("[Scheduler] 问答对加密错误")
            return

        # 构建记录对象
        record = self._build_record(encrypt_data, encrypt_config, current_time)

        # 保存记录
        if self.post_body.conversation_id:
            await RecordManager.insert_record_data(
                self.task.metadata.userId,
                self.post_body.conversation_id,
                record,
            )

    async def _handle_task_state(self) -> None:
        """根据任务状态判断删除或保存Task"""
        task = self.task

        if not task.state or task.state.executorStatus in [
            ExecutorStatus.SUCCESS,
            ExecutorStatus.ERROR,
            ExecutorStatus.CANCELLED,
        ]:
            await TaskManager.delete_task_by_task_id(task.metadata.id)
        else:
            await TaskManager.save_task(task)

    async def _ensure_conversation_exists(self) -> None:
        """确保存在conversation，如果不存在则创建"""
        # 如果已经有 conversation_id，无需创建
        if self.task.metadata.conversationId:
            return

        _logger.info("[Scheduler] 当前无 conversation_id，创建新对话")

        # 确定标题：直接使用问题的前 _CONVERSATION_TITLE_MAX_LENGTH 个字符
        title = ""
        if hasattr(self.task.runtime, "question"):
            question_attr = getattr(self.task.runtime, "question", "")
            if question_attr and isinstance(question_attr, str):
                question = question_attr.strip()
                if question:
                    # 截取前 N 个字符作为标题
                    if len(question) > _CONVERSATION_TITLE_MAX_LENGTH:
                        title = question[:_CONVERSATION_TITLE_MAX_LENGTH] + "..."
                    else:
                        title = question

        # 确定 app_id
        app_id: uuid.UUID | None = None
        if self.post_body.app and self.post_body.app.app_id:
            app_id = self.post_body.app.app_id

        # 确定是否为调试模式
        debug = getattr(self.post_body, "debug", False)

        try:
            # 调用 InitMixin 中的 _create_new_conversation 方法创建对话
            new_conversation: Conversation = await self._create_new_conversation(  # type: ignore[attr-defined]
                title=title,
                user_id=self.task.metadata.userId,
                app_id=app_id,
                debug=debug,
            )

            # 更新 task 和 post_body 中的 conversation_id
            self.task.metadata.conversationId = new_conversation.id
            self.post_body.conversation_id = new_conversation.id

            _logger.info(
                "[Scheduler] 成功创建新对话，conversation_id: %s, title: %s",
                new_conversation.id,
                title,
            )
        except Exception:
            _logger.exception("[Scheduler] 创建新对话失败")
            raise

    async def _save_data(self) -> None:
        """保存当前Executor、Task、Record等的数据"""
        task = self.task
        record_group = None

        used_docs = self._extract_used_documents()

        record_content = self._build_record_content()

        if task.state:
            await TaskManager.save_flow_context(task.context)

        # 在保存 Record 之前，确保存在 conversation
        await self._ensure_conversation_exists()

        current_time = round(datetime.now(UTC).timestamp(), 2)

        await self._handle_document_management(record_group, used_docs)
        await self._save_record_data(record_content, current_time)

        # 更新应用中心最近使用的应用
        if self.post_body.app and self.post_body.app.app_id:
            await AppCenterManager.update_recent_app(self.task.metadata.userId, self.post_body.app.app_id)

        await self._handle_task_state()
