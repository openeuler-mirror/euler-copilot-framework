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

    async def _save_data(self) -> None:
        """保存当前Executor、Task、Record等的数据"""
        task = self.task
        user_id = self.task.metadata.userId
        post_body = self.post_body

        used_docs = []
        record_group = None  # TODO: 需要从适当的地方获取record_group

        if hasattr(task.runtime, "documents") and task.runtime.documents:
            for docs in task.runtime.documents:
                doc_dict = docs if isinstance(docs, dict) else (docs.model_dump() if hasattr(docs, "model_dump") else docs)
                used_docs.append(doc_dict)

        record_content = RecordContent(
            question=task.runtime.question if hasattr(task.runtime, "question") else "",
            answer=task.runtime.answer if hasattr(task.runtime, "answer") else "",
            facts=task.runtime.facts if hasattr(task.runtime, "facts") else [],
            data={},
        )

        try:
            encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
        except Exception:
            _logger.exception("[Scheduler] 问答对加密错误")
            return

        if task.state:
            await TaskManager.save_flow_context(task.context)

        current_time = round(datetime.now(UTC).timestamp(), 2)
        record = Record(
            id=task.metadata.id,
            conversationId=task.metadata.conversationId,
            taskId=task.metadata.id,
            userId=user_id,
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

        if record_group and post_body.conversation_id:
            await DocumentManager.change_doc_status(user_id, post_body.conversation_id, record_group)

        if post_body.conversation_id:
            await RecordManager.insert_record_data(user_id, post_body.conversation_id, record)

        if record_group and used_docs:
            await DocumentManager.save_answer_doc(user_id, record_group, used_docs)

        if post_body.app and post_body.app.app_id:
            await AppCenterManager.update_recent_app(user_id, post_body.app.app_id)

        if not task.state or task.state.flow_status in [StepStatus.SUCCESS, StepStatus.ERROR, StepStatus.CANCELLED]:
            await TaskManager.delete_task_by_task_id(task.metadata.id)
        else:
            await TaskManager.save_task(task.metadata.id, task.metadata)
            await TaskManager.save_task_runtime(task.runtime)
            if task.state:
                await TaskManager.save_executor_checkpoint(task.state)
