"""用户资产库管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from typing import Optional

from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """用户资产库管理"""

    @staticmethod
    async def change_kb_id(user_sub: str, kb_id: str) -> bool:
        """修改当前用户的知识库ID"""
        user_collection = MongoDB.get_collection("user")
        try:
            user = await user_collection.find_one({"_id": user_sub}, {"kb_id": 1})
            if user is None:
                logger.error("[KnowledgeBaseManager] 修改知识库ID失败: 用户不存在")
                return False
            await user_collection.update_one({"_id": user_sub}, {"$set": {"kb_id": kb_id}})
            return True
        except Exception:
            logger.exception("[KnowledgeBaseManager] 修改知识库ID失败")
            return False

    @staticmethod
    async def get_kb_id(user_sub: str) -> Optional[str]:
        """获取当前用户的知识库ID"""
        user_collection = MongoDB.get_collection("user")
        try:
            user_info = await user_collection.find_one({"_id": user_sub}, {"kb_id": 1})
            if not user_info:
                logger.error("[KnowledgeBaseManager] 用户不存在: %s", user_sub)
                return None
            return user_info["kb_id"]
        except Exception:
            logger.exception("[KnowledgeBaseManager] 获取知识库ID失败")
            return None
