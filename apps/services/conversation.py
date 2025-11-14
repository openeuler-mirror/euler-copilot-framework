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
from apps.llm.adapters import get_provider_from_endpoint
from apps.llm.schema import DefaultModelId

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    @staticmethod
    async def get_conversation_by_user_sub(user_sub: str) -> list[Conversation]:
        """根据用户ID获取对话列表，按时间由近到远排序"""
        conv_collection = MongoDB.get_collection("conversation")
        return [
            Conversation(**conv)
            async for conv in conv_collection.find({"user_sub": user_sub, "debug": False}).sort({"created_at": 1})
        ]

    @staticmethod
    async def get_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> Conversation | None:
        """通过ConversationID查询对话信息"""
        conv_collection = MongoDB.get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            return None
        return Conversation.model_validate(result)

    @staticmethod
    async def add_conversation_by_user_sub(
            title: str,
            user_sub: str, app_id: str, llm_id: str, kb_ids: list[str],
            *, debug: bool) -> Conversation | None:
        """通过用户ID新建对话"""
        if not llm_id:
            # 获取系统默认模型的UUID
            llm = await LLMManager.get_llm_by_id(DefaultModelId.DEFAULT_CHAT_MODEL_ID.value)
            llm_item = LLMItem(
                llm_id=llm.id,
                model_name=llm.model_name,
                icon=llm.icon,
            )
        else:
            # 首先尝试通过用户ID和LLM ID查找
            default_model_ids = [item.value for item in DefaultModelId]
            if llm_id in default_model_ids:
                llm = await LLMManager.get_llm_by_id(llm_id)
            else:
                try:
                    llm = await LLMManager.get_llm_by_user_sub_and_id(user_sub, llm_id)
                except ValueError:
                    # 如果用户级别的LLM不存在，尝试查找系统级别的LLM
                    logger.info(
                        f"[ConversationManager] 用户级别LLM {llm_id} 不存在，尝试查找系统级别LLM")
            if llm is None:
                logger.error("[ConversationManager] 获取大模型失败")
                return None
            llm_item = LLMItem(
                llm_id=llm.id,
                model_name=llm.model_name,
                icon=llm.icon,
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
            title=title,
            user_sub=user_sub,
            app_id=app_id,
            llm=llm_item,
            kb_list=kb_item_list,
            debug=debug if debug else False,
        )
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                conv_collection = MongoDB.get_collection("conversation")
                await conv_collection.insert_one(conv.model_dump(by_alias=True), session=session)
                user_collection = MongoDB.get_collection("user")
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
        conv_collection = MongoDB.get_collection("conversation")
        result = await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": data},
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> None:
        """通过ConversationID删除对话"""
        user_collection = MongoDB.get_collection("user")
        conv_collection = MongoDB.get_collection("conversation")
        record_group_collection = MongoDB.get_collection("record_group")

        # 🔑 修正：获取所有需要清理的文件ID
        files_to_cleanup = []

        # 1. 获取未转为历史记录的文件（unused_docs）
        conversation_data = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if conversation_data:
            unused_docs = conversation_data.get("unused_docs", [])
            files_to_cleanup.extend(unused_docs)

        # 2. 获取历史记录中绑定的文件
        async for record_group in record_group_collection.find({"conversation_id": conversation_id}):
            docs = record_group.get("docs", [])
            for doc in docs:
                if "id" in doc:  # RecordGroupDocument 格式
                    files_to_cleanup.append(doc["id"])
                elif "_id" in doc:
                    files_to_cleanup.append(doc["_id"])

        async with MongoDB.get_session() as session, await session.start_transaction():
            await conv_collection.delete_one(
                {"_id": conversation_id, "user_sub": user_sub}, session=session,
            )

            await user_collection.update_one(
                {"_id": user_sub}, {"$pull": {"conversations": conversation_id}}, session=session,
            )
            await record_group_collection.delete_many({"conversation_id": conversation_id}, session=session)
            await session.commit_transaction()

        # 🔑 修正：清理对话关联的所有文件（包括历史记录中的）
        if files_to_cleanup:
            try:
                from apps.services.document import DocumentManager
                # 去重文件ID
                unique_file_ids = list(set(files_to_cleanup))
                await DocumentManager.delete_document(user_sub, unique_file_ids)
                logger.info(
                    f"已清理对话 {conversation_id} 的 {len(unique_file_ids)} 个文件")
            except Exception as e:
                logger.error(f"清理对话文件失败: {e}")

        # 🔑 修正：清理对话变量池中的文件变量（但不清理已转为历史记录的文件）
        try:
            from apps.scheduler.variable.pool_manager import get_pool_manager
            pool_manager = await get_pool_manager()

            # 获取对话变量池中的文件变量，清理其引用的文件
            conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
            if conversation_pool:
                await _cleanup_transient_file_variables_in_pool(conversation_pool, user_sub, files_to_cleanup)

            # 移除对话变量池
            await pool_manager.remove_conversation_pool(conversation_id)
            logger.info(f"已清理对话变量池: {conversation_id}")
        except Exception as e:
            logger.error(f"清理对话变量池失败: {e}")

        await TaskManager.delete_tasks_and_flow_context_by_conversation_id(conversation_id)


async def _cleanup_transient_file_variables_in_pool(pool, user_sub: str, already_cleaned_files: list[str]) -> None:
    """清理变量池中文件变量引用的文件资源（排除已经被历史记录清理的文件）"""
    try:
        from apps.scheduler.variable.type import VariableType
        from apps.services.document import DocumentManager

        variables = await pool.list_variables()
        file_ids_to_cleanup = []

        for variable in variables:
            if variable.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                if isinstance(variable.value, dict):
                    if variable.metadata.var_type == VariableType.FILE:
                        file_id = variable.value.get("file_id")
                        if file_id and file_id not in already_cleaned_files:
                            file_ids_to_cleanup.append(file_id)
                    else:  # ARRAY_FILE
                        file_ids = variable.value.get("file_ids", [])
                        for file_id in file_ids:
                            if file_id not in already_cleaned_files:
                                file_ids_to_cleanup.append(file_id)

        # 批量删除文件（排除重复）
        unique_file_ids = list(set(file_ids_to_cleanup))
        if unique_file_ids:
            await DocumentManager.delete_document(user_sub, unique_file_ids)
            logger.info(f"已清理变量池中的 {len(unique_file_ids)} 个暂态文件")

    except Exception as e:
        logger.error(f"清理变量池暂态文件失败: {e}")
