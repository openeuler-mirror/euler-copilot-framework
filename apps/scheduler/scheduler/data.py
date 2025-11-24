# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""数据管理相关的Mixin类"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from apps.common.security import Security
from apps.models import ExecutorStatus
from apps.models import Record as PgRecord
from apps.models import RecordMetadata as PgRecordMetadata
from apps.schemas.record import RecordContent
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.appcenter import AppCenterManager
from apps.services.document import DocumentManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

_logger = logging.getLogger(__name__)


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

    def _build_record(
        self,
        encrypt_data: str,
        encrypt_config: dict[str, Any],
        current_time: float,
    ) -> tuple[PgRecord, PgRecordMetadata]:
        """构建记录对象和元数据对象"""
        task = self.task
        user_id = task.metadata.userId
        record_id = task.metadata.id

        pg_record = PgRecord(
            id=record_id,
            conversationId=task.metadata.conversationId,
            taskId=task.metadata.id,
            userId=user_id,
            content=encrypt_data,
            key=encrypt_config,
            createdAt=datetime.fromtimestamp(current_time, tz=UTC),
        )

        pg_metadata = PgRecordMetadata(
            recordId=record_id,
            timeCost=0,
            inputTokens=0,
            outputTokens=0,
        )

        return pg_record, pg_metadata

    async def _handle_document_management(self, used_docs: list[dict], record_id: UUID) -> None:
        """处理文档管理相关操作"""
        user_id = self.task.metadata.userId
        post_body = self.post_body

        if post_body.conversation_id:
            await DocumentManager.change_doc_status(user_id, post_body.conversation_id)

        if used_docs:
            await DocumentManager.save_answer_doc(user_id, record_id, used_docs)

    async def _save_record_data(self, record_content: RecordContent, current_time: float) -> UUID | None:
        """加密并保存记录数据,返回记录ID"""
        # 加密记录内容
        try:
            encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
        except Exception:
            _logger.exception("[Scheduler] 问答对加密错误")
            return None

        # 构建记录对象和元数据对象
        pg_record, pg_metadata = self._build_record(encrypt_data, encrypt_config, current_time)

        # 保存记录
        if self.post_body.conversation_id:
            await RecordManager.insert_record_data(
                self.task.metadata.userId,
                self.post_body.conversation_id,
                pg_record,
                pg_metadata,
            )
            return pg_record.id
        return None

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

    async def _save_data(self) -> None:
        """保存当前Executor、Task、Record等的数据"""
        task = self.task

        used_docs = self._extract_used_documents()

        record_content = self._build_record_content()

        # 先处理任务状态（删除或保存Task）
        await self._handle_task_state()

        # 再保存flow context
        if task.state:
            await TaskManager.save_flow_context(task.context)

        current_time = round(datetime.now(UTC).timestamp(), 2)
        # 先保存record,获取record_id
        record_id = await self._save_record_data(record_content, current_time)
        # 再处理文档管理,传入record_id
        if record_id:
            await self._handle_document_management(used_docs, record_id)

        # 更新应用中心最近使用的应用
        if self.post_body.app and self.post_body.app.app_id:
            await AppCenterManager.update_recent_app(self.task.metadata.userId, self.post_body.app.app_id)
