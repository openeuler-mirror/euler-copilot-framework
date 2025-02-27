"""审计日志Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging

from apps.entities.collection import Audit
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)

class AuditLogManager:
    """审计日志相关操作"""

    @staticmethod
    async def add_audit_log(data: Audit) -> bool:
        """EulerCopilot审计日志

        :param data: 审计日志数据
        :return: 是否添加成功；True/False
        """
        try:
            collection = MongoDB.get_collection("audit")
            await collection.insert_one(data.model_dump(by_alias=True))
            return True
        except Exception:
            logger.exception("[AuditLogManager] 添加审计日志失败")
            return False
