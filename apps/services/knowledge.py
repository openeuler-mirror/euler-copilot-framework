# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户资产库管理"""

import logging
from typing import Any

import httpx
from fastapi import status

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.schemas.collection import KnowledgeBaseItem
from apps.schemas.response_data import KnowledgeBaseItem as KnowledgeBaseItemResponse
from apps.schemas.response_data import TeamKnowledgeBaseItem
from apps.services.session import SessionManager

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """用户资产库管理"""

    @staticmethod
    async def get_kb_ids_by_conversation_id(user_sub: str, conversation_id: str) -> list[str]:
        """
        通过对话ID获取知识库ID

        :param user_sub: 用户ID
        :param conversation_id: 对话ID
        :return: 知识库ID列表
        """
        conv_collection = MongoDB.get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            err_msg = "[KnowledgeBaseManager] 获取知识库ID失败，未找到对话"
            logger.error(err_msg)
            return []
        kb_config_list = result.get("kb_list", [])
        return [kb_config["kb_id"] for kb_config in kb_config_list]

    @staticmethod
    async def get_team_kb_list_from_rag(
        user_sub: str,
        kb_id: str | None = None,
        kb_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        从RAG获取知识库列表

        :param user_sub: 用户sub
        :param kb_id: 知识库ID
        :param kb_name: 知识库名称
        :return: 知识库列表
        """
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = Config().get_config().rag.rag_service.rstrip("/")+"/kb"
        headers = {
            "Authorization": f"Bearer {session_id}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            data = {
                "kbName": kb_name,
            }
            if kb_id:
                data["kbId"] = kb_id
            resp = await client.get(url, headers=headers, params=data, timeout=30.0)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
        return resp_data["result"]["teamKnowledgebases"]

    @staticmethod
    async def list_team_kb(
            user_sub: str, conversation_id: str, kb_id: str, kb_name: str) -> list[KnowledgeBaseItemResponse]:
        """
        获取当前用户的知识库ID

        :param user_sub: 用户sub
        :return: 知识库ID列表
        """
        conv_collection = MongoDB.get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            err_msg = "[KnowledgeBaseManager] 获取知识库ID失败，未找到对话"
            logger.error(err_msg)
            return []
        kb_config_list = result.get("kb_list", [])
        kb_ids_used = [kb_config["kb_id"] for kb_config in kb_config_list]
        kb_ids_used = set(kb_ids_used)

        team_kb_item_list = []
        try:
            team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, kb_id, kb_name)
        except Exception as e:
            logger.error(f"[KnowledgeBaseManager] 获取团队知识库列表失败: {e}")
            return []
        for team_kb in team_kb_list:
            team_kb_item = TeamKnowledgeBaseItem(
                teamId=team_kb["teamId"],
                teamName=team_kb["teamName"],
            )
            for kb in team_kb["kbList"]:
                kb_item = KnowledgeBaseItemResponse(
                    kbId=kb["kbId"],
                    kbName=kb["kbName"],
                    description=kb["description"],
                    isUsed=kb["kbId"] in kb_ids_used,
                )
                team_kb_item.kb_list.append(kb_item)
            team_kb_item_list.append(team_kb_item)
        return team_kb_item_list

    @staticmethod
    async def update_conv_kb(
        user_sub: str,
        conversation_id: str,
        kb_ids: list[str],
    ) -> list[str]:
        """
        更新对话的知识库列表

        :param user_sub: 用户sub
        :param conversation_id: 对话ID
        :param kb_list: 知识库列表
        :return: 是否更新成功
        """
        kb_ids = list(set(kb_ids))
        conv_collection = MongoDB.get_collection("conversation")
        conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not conv_dict:
            err_msg = "[KnowledgeBaseManager] 更新知识库失败，未找到对话"
            logger.error(err_msg)
            return []
        kb_ids_update_success = []
        kb_item_dict_list = []
        try:
            team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, None, None)
        except Exception as e:
            logger.error(f"[KnowledgeBaseManager] 获取团队知识库列表失败: {e}")
            team_kb_list = []
        for team_kb in team_kb_list:
            for kb in team_kb["kbList"]:
                if str(kb["kbId"]) in kb_ids:
                    kb_item = KnowledgeBaseItem(
                        kb_id=kb["kbId"],
                        kb_name=kb["kbName"],
                    )
                    kb_item_dict_list.append(kb_item.model_dump(by_alias=True))
                    kb_ids_update_success.append(kb["kbId"])
        await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": {"kb_list": kb_item_dict_list}},
        )
        return kb_ids_update_success
