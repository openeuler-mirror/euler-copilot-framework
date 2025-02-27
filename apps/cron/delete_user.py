"""删除30天未登录用户

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from datetime import datetime, timedelta, timezone

import asyncer

from apps.entities.collection import Audit
from apps.manager.audit_log import AuditLogManager
from apps.manager.user import UserManager
from apps.models.mongo import MongoDB
from apps.service.knowledge_base import KnowledgeBaseService

logger = logging.getLogger("ray")

class DeleteUserCron:
    """删除30天未登录用户"""

    @staticmethod
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
                await KnowledgeBaseService.delete_doc_from_rag(docs)
            except Exception:
                logger.exception("[DeleteUserCron] 自动删除用户 %s 文档失败", user_id)

            audit_log = Audit(
                user_sub=user_id,
                http_method="DELETE",
                module="user",
                message=f"Automatic deleted user: {user_id}, for inactive more than 30 days",
            )
            await AuditLogManager.add_audit_log(audit_log)


    @staticmethod
    def delete_user() -> None:
        """删除用户"""
        try:
            timepoint = datetime.now(timezone.utc) - timedelta(days=30)
            timestamp = timepoint.timestamp()

            asyncer.syncify(DeleteUserCron._delete_user)(timestamp)
        except Exception:
            logger.exception("[DeleteUserCron] 自动删除用户失败")
