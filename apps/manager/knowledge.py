"""用户资产库管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.constants import LOGGER
from apps.models.mongo import MongoDB


class KnowledgeBaseManager:
    """用户资产库管理"""

    @staticmethod
    async def change_kb_id(user_sub: str, kb_id: str) -> bool:
        """修改当前用户的知识库ID"""
        user_collection = MongoDB.get_collection("user")
        try:
            user = await user_collection.find_one({"_id": user_sub}, {"kb_id": 1})
            if user is None:
                LOGGER.error("[KnowledgeBaseManager] change kb_id error: user_sub not found")
                return False
            await user_collection.update_one({"_id": user_sub}, {"$set": {"kb_id": kb_id}})
            return True
        except Exception as e:
            LOGGER.error(f"[KnowledgeBaseManager] change kb_id error: {e}")
            return False

    @staticmethod
    async def get_kb_id(user_sub: str) -> Optional[str]:
        """获取当前用户的知识库ID"""
        user_collection = MongoDB.get_collection("user")
        try:
            user_info = await user_collection.find_one({"_id": user_sub}, {"kb_id": 1})
            if not user_info:
                LOGGER.error("[KnowledgeBaseManager] User not found: %s", user_sub)
                return None
            return user_info["kb_id"]
        except Exception as e:
            LOGGER.error(f"[KnowledgeBaseManager] get kb_id error: {e}")
            return None
