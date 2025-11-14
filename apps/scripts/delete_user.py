# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""删除30天未登录用户"""

import logging
from datetime import UTC, datetime, timedelta

import asyncer

from apps.schemas.collection import Audit
from apps.services.audit_log import AuditLogManager
from apps.services.user import UserManager
from apps.services.session import SessionManager
from apps.common.mongo import MongoDB
from apps.services.knowledge_base import KnowledgeBaseService

logger = logging.getLogger(__name__)


async def _delete_user(timestamp: float) -> None:
    """异步删除用户"""
    user_ids = await UserManager.query_userinfo_by_login_time(timestamp)
    for user_id in user_ids:
        await UserManager.delete_userinfo_by_user_sub(user_id)
        # 查找用户关联的文件
        doc_collection = MongoDB.get_collection("document")
        docs = [doc["_id"] async for doc in doc_collection.find({"user_sub": user_id})]
        # 删除文件
        try:
            await doc_collection.delete_many({"_id": {"$in": docs}})
            session_id = await SessionManager.get_session_by_user_sub(user_id)
            await KnowledgeBaseService.delete_doc_from_rag(session_id, docs)
        except Exception:
            logger.exception("[DeleteUserCron] 自动删除用户 %s 文档失败", user_id)
        audit_log = Audit(
            user_sub=user_id,
            http_method="DELETE",
            module="user",
            message=f"Automatic deleted user: {user_id}, for inactive more than 30 days",
        )
        await AuditLogManager.add_audit_log(audit_log)


if __name__ == "__main__":
    """删除用户"""
    try:
        timepoint = datetime.now(UTC) - timedelta(days=30)
        timestamp = timepoint.timestamp()
        asyncer.syncify(_delete_user)(timestamp)
    except Exception:
        logger.exception("[DeleteUserCron] 自动删除用户失败")
