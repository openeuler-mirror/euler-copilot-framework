# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对话 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.schemas.collection import Conversation, KnowledgeBaseItem, LLMItem
from apps.services.knowledge import KnowledgeBaseManager
from apps.services.llm import LLMManager
from apps.services.task import TaskManager
from apps.templates.generate_llm_operator_config import llm_provider_dict

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    @staticmethod
    async def get_conversation_by_user_sub(user_sub: str) -> list[Conversation]:
        """根据用户ID获取对话列表，按时间由近到远排序"""
        conv_collection = MongoDB().get_collection("conversation")
        return [
            Conversation(**conv)
            async for conv in conv_collection.find({"user_sub": user_sub, "debug": False}).sort({"created_at": 1})
        ]

    @staticmethod
    async def get_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> Conversation | None:
        """通过ConversationID查询对话信息"""
        conv_collection = MongoDB().get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            return None
        return Conversation.model_validate(result)

    @staticmethod
    async def add_conversation_by_user_sub(
            user_sub: str, app_id: str, llm_id: str, kb_ids: list[str],
            *, debug: bool) -> Conversation | None:
        """通过用户ID新建对话"""
        if llm_id == "empty":
            llm_item = LLMItem(
                llm_id="empty",
                model_name=Config().get_config().llm.model,
                icon=llm_provider_dict["ollama"]["icon"],
            )
        else:
            llm = await LLMManager.get_llm_by_id(user_sub, llm_id)
            if llm is None:
                logger.error("[ConversationManager] 获取大模型失败")
                return None
            llm_item = LLMItem(
                llm_id=llm.id,
                model_name=llm.model_name,
            )
        kb_item_list = []
        try:
            team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, None, None)
        except:
            logger.error("[ConversationManager] 获取团队知识库列表失败")
            team_kb_list = []
        for team_kb in team_kb_list:
            for kb in team_kb["kbList"]:
                if str(kb["kbId"]) in kb_ids:
                    kb_item = KnowledgeBaseItem(
                        kb_id=kb["kbId"],
                        kb_name=kb["kbName"],
                    )
                    kb_item_list.append(kb_item)
        conversation_id = str(uuid.uuid4())
        conv = Conversation(
            _id=conversation_id,
            user_sub=user_sub,
            app_id=app_id,
            llm=llm_item,
            kb_list=kb_item_list,
            debug=debug if debug else False,
        )
        mongo = MongoDB()
        try:
            async with mongo.get_session() as session, await session.start_transaction():
                conv_collection = mongo.get_collection("conversation")
                await conv_collection.insert_one(conv.model_dump(by_alias=True), session=session)
                user_collection = mongo.get_collection("user")
                update_data: dict[str, dict[str, Any]] = {
                    "$push": {"conversations": conversation_id},
                }
                if app_id:
                    # 非调试模式下更新应用使用情况
                    if not debug:
                        update_data["$set"] = {
                            f"app_usage.{app_id}.last_used": round(datetime.now(UTC).timestamp(), 3),
                        }
                        update_data["$inc"] = {f"app_usage.{app_id}.count": 1}
                    await user_collection.update_one(
                        {"_id": user_sub},
                        update_data,
                        session=session,
                    )
                    await session.commit_transaction()
                return conv
        except Exception:
            logger.exception("[ConversationManager] 新建对话失败")
            return None

    @staticmethod
    async def update_conversation_by_conversation_id(user_sub: str, conversation_id: str, data: dict[str, Any]) -> bool:
        """通过ConversationID更新对话信息"""
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        result = await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": data},
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> None:
        """通过ConversationID删除对话"""
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        conv_collection = mongo.get_collection("conversation")
        record_group_collection = mongo.get_collection("record_group")

        async with mongo.get_session() as session, await session.start_transaction():
            conversation_data = await conv_collection.find_one_and_delete(
                {"_id": conversation_id, "user_sub": user_sub}, session=session,
            )
            if not conversation_data:
                return

            await user_collection.update_one(
                {"_id": user_sub}, {"$pull": {"conversations": conversation_id}}, session=session,
            )
            await record_group_collection.delete_many({"conversation_id": conversation_id}, session=session)
            await session.commit_transaction()

        await TaskManager.delete_tasks_and_flow_context_by_conversation_id(conversation_id)
