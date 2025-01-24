"""对话 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from apps.constants import LOGGER
from apps.entities.collection import Conversation
from apps.manager.task import TaskManager
from apps.models.mongo import MongoDB


class ConversationManager:
    """对话管理器"""

    @staticmethod
    async def get_conversation_by_user_sub(user_sub: str) -> list[Conversation]:
        """根据用户ID获取对话列表，按时间由近到远排序"""
        try:
            conv_collection = MongoDB.get_collection("conversation")
            return [Conversation(**conv) async for conv in conv_collection.find({"user_sub": user_sub}).sort({"created_at": 1})]
        except Exception as e:
            LOGGER.info(f"[ConversationManager] Get conversation by user_sub failed: {e}")
        return []

    @staticmethod
    async def get_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> Optional[Conversation]:
        """通过ConversationID查询对话信息"""
        try:
            conv_collection = MongoDB.get_collection("conversation")
            result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not result:
                return None
            return Conversation.model_validate(result)
        except Exception as e:
            LOGGER.info(f"[ConversationManager] Get conversation by conversation_id failed: {e}")
            return None

    @staticmethod
    async def add_conversation_by_user_sub(user_sub: str, app_id: str, *, is_debug: bool) -> Optional[Conversation]:
        """通过用户ID新建对话"""
        conversation_id = str(uuid.uuid4())
        conv = Conversation(
            _id=conversation_id,
            user_sub=user_sub,
            app_id=app_id,
            is_debug=is_debug,
        )
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                conv_collection = MongoDB.get_collection("conversation")
                await conv_collection.insert_one(conv.model_dump(by_alias=True), session=session)
                user_collection = MongoDB.get_collection("user")
                await user_collection.update_one(
                    {"_id": user_sub},
                    {
                        "$push": {"conversations": conversation_id},
                        "$set": {f"app_usage.{app_id}.last_used": round(datetime.now(timezone.utc).timestamp(), 3)},
                        "$inc": {f"app_usage.{app_id}.count": 1},
                    },
                    session=session,
                )
                await session.commit_transaction()
                return conv
        except Exception as e:
            LOGGER.info(f"[ConversationManager] Add conversation by user_sub failed: {e}")
            return None

    @staticmethod
    async def update_conversation_by_conversation_id(user_sub: str, conversation_id: str, data: dict[str, Any]) -> bool:
        """通过ConversationID更新对话信息"""
        try:
            conv_collection = MongoDB.get_collection("conversation")
            result = await conv_collection.update_one(
                {"_id": conversation_id, "user_sub": user_sub},
                {"$set": data},
            )
            return result.modified_count > 0
        except Exception as e:
            LOGGER.info(f"[ConversationManager] Update conversation by conversation_id failed: {e}")
            return False

    @staticmethod
    async def delete_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> bool:
        """通过ConversationID删除对话"""
        user_collection = MongoDB.get_collection("user")
        conv_collection = MongoDB.get_collection("conversation")
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                conversation_data = await conv_collection.find_one_and_delete({"_id": conversation_id, "user_sub": user_sub}, session=session)
                if not conversation_data:
                    return False

                await user_collection.update_one({"_id": user_sub}, {"$pull": {"conversations": conversation_id}}, session=session)
                await record_group_collection.delete_many({"conversation_id": conversation_id}, session=session)
                await session.commit_transaction()
            await TaskManager.delete_tasks_by_conversation_id(conversation_id)
            return True
        except Exception as e:
            LOGGER.info(f"[ConversationManager] Delete conversation by conversation_id failed: {e}")
            return False
