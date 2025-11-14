# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""审计日志Manager"""

import logging

from apps.common.mongo import MongoDB
from apps.schemas.collection import Audit

logger = logging.getLogger(__name__)

class AuditLogManager:
    """审计日志相关操作"""

    @staticmethod
    async def add_audit_log(data: Audit) -> None:
        """
        EulerCopilot审计日志

        :param data: 审计日志数据
        """
        collection = MongoDB.get_collection("audit")
        await collection.insert_one(data.model_dump(by_alias=True))
