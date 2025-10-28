# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""数据管理相关的Mixin类"""

import logging
from datetime import UTC, datetime

from apps.common.security import Security
from apps.models import Record, RecordMetadata, StepStatus
from apps.schemas.record import FlowHistory, RecordContent
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

        if hasattr(task.runtime, "documents") and task.runtime.documents:
            for docs in task.runtime.documents:
                doc_dict = docs if isinstance(docs, dict) else (docs.model_dump() if hasattr(docs, "model_dump") else docs)
                used_docs.append(doc_dict)

        return used_docs

    def _build_record_content(self) -> RecordContent:
        """构建记录内容对象"""
        task = self.task

        return RecordContent(
            question=task.runtime.question if hasattr(task.runtime, "question") else "",
            answer=task.runtime.answer if hasattr(task.runtime, "answer") else "",
            facts=task.runtime.facts if hasattr(task.runtime, "facts") else [],
            data={},
        )

    def _encrypt_record_content(self, record_content: RecordContent) -> tuple[str, str] | None:
        """加密记录内容"""
        try:
            encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
            return encrypt_data, encrypt_config
        except Exception:
            _logger.exception("[Scheduler] 问答对加密错误")
            return None

    def _build_record(self, encrypt_data: str, encrypt_config: str, current_time: float) -> Record:
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
            flow=FlowHistory(
                flow_id=task.state.flow_id if task.state else "",
                flow_name=task.state.flow_name if task.state else "",
                flow_status=task.state.flow_status if task.state else StepStatus.SUCCESS,
                history_ids=[context.id for context in task.context],
            ) if task.state else None,
        )

    async def _handle_document_management(self, record_group: str | None, used_docs: list[dict]) -> None:
        """处理文档管理相关操作"""
        user_id = self.task.metadata.userId
        post_body = self.post_body

        if record_group and post_body.conversation_id:
            await DocumentManager.change_doc_status(user_id, post_body.conversation_id, record_group)

        if record_group and used_docs:
            await DocumentManager.save_answer_doc(user_id, record_group, used_docs)

    async def _save_record_data(self, record: Record) -> None:
        """保存记录数据"""
        user_id = self.task.metadata.userId
        post_body = self.post_body

        if post_body.conversation_id:
            await RecordManager.insert_record_data(user_id, post_body.conversation_id, record)

    async def _update_app_center(self) -> None:
        """更新应用中心最近使用的应用"""
        user_id = self.task.metadata.userId
        post_body = self.post_body

        if post_body.app and post_body.app.app_id:
            await AppCenterManager.update_recent_app(user_id, post_body.app.app_id)

    async def _handle_task_state(self) -> None:
        """处理任务状态管理"""
        task = self.task

        if not task.state or task.state.flow_status in [StepStatus.SUCCESS, StepStatus.ERROR, StepStatus.CANCELLED]:
            await TaskManager.delete_task_by_task_id(task.metadata.id)
        else:
            await TaskManager.save_task(task.metadata.id, task.metadata)
            await TaskManager.save_task_runtime(task.runtime)
            if task.state:
                await TaskManager.save_executor_checkpoint(task.state)

    async def _save_data(self) -> None:
        """保存当前Executor、Task、Record等的数据"""
        task = self.task
        record_group = None

        used_docs = self._extract_used_documents()

        record_content = self._build_record_content()
        encrypted_result = self._encrypt_record_content(record_content)
        if encrypted_result is None:
            return
        encrypt_data, encrypt_config = encrypted_result

        if task.state:
            await TaskManager.save_flow_context(task.context)

        current_time = round(datetime.now(UTC).timestamp(), 2)
        record = self._build_record(encrypt_data, encrypt_config, current_time)

        await self._handle_document_management(record_group, used_docs)

        await self._save_record_data(record)

        await self._update_app_center()

        await self._handle_task_state()
