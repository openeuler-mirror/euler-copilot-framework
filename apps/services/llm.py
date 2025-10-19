# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.schemas.collection import LLM, LLMItem
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import LLMProvider, LLMProviderInfo
from apps.templates.generate_llm_operator_config import llm_provider_dict

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

    @staticmethod
    async def list_llm_provider() -> list[LLMProvider]:
        """
        获取大模型提供商列表

        :return: 大模型提供商列表
        """
        provider_list = []
        for provider in llm_provider_dict.values():
            item = LLMProvider(
                provider=provider["provider"],
                url=provider["url"],
                description=provider["description"],
                icon=provider["icon"],
            )
            provider_list.append(item)
        return provider_list

    @staticmethod
    async def get_llm_id_by_conversation_id(user_sub: str, conversation_id: str) -> str:
        """
        通过对话ID获取大模型ID

        :param user_sub: 用户ID
        :param conversation_id: 对话ID
        :return: 大模型ID
        """
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            return ""
        return result.get("llm", {}).get("llm_id", "")

    @staticmethod
    async def get_llm_by_id(llm_id: str) -> LLM:
        """
        通过ID获取大模型

        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        llm_collection = MongoDB().get_collection("llm")
        result = await llm_collection.find_one({"_id": llm_id})
        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        return LLM.model_validate(result)

    @staticmethod
    async def get_llm_by_user_sub_and_id(user_sub: str, llm_id: str) -> LLM:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        llm_collection = MongoDB().get_collection("llm")
        result = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        return LLM.model_validate(result)

    @staticmethod
    async def list_llm(user_sub: str, llm_id: str | None) -> list[LLMProviderInfo]:
        """
        获取大模型列表

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型列表
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")

        query = {"user_sub": user_sub}
        if llm_id:
            query["llm_id"] = llm_id
        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)

        llm_item = LLMProviderInfo(
            llmId="empty",
            icon=llm_provider_dict["ollama"]["icon"],
            openaiBaseUrl=Config().get_config().llm.endpoint,
            openaiApiKey=Config().get_config().llm.key,
            modelName=Config().get_config().llm.model,
            maxTokens=Config().get_config().llm.max_tokens,
            isEditable=False,
        )
        llm_list = [llm_item]
        for llm in result:
            llm_item = LLMProviderInfo(
                llmId=llm["_id"],
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def update_llm(user_sub: str, llm_id: str | None, req: UpdateLLMReq) -> str:
        """
        创建大模型

        :param user_sub: 用户ID
        :param req: 创建大模型请求体
        :return: 大模型对象
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")

        if llm_id:
            llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)
            llm = LLM(
                _id=llm_id,
                user_sub=user_sub,
                icon=llm_dict["icon"],
                openai_base_url=req.openai_base_url,
                openai_api_key=req.openai_api_key,
                model_name=req.model_name,
                max_tokens=req.max_tokens,
            )
            await llm_collection.update_one({"_id": llm_id}, {"$set": llm.model_dump(by_alias=True)})
        else:
            llm = LLM(
                user_sub=user_sub,
                icon=req.icon,
                openai_base_url=req.openai_base_url,
                openai_api_key=req.openai_api_key,
                model_name=req.model_name,
                max_tokens=req.max_tokens,
            )
            await llm_collection.insert_one(llm.model_dump(by_alias=True))
        return llm.id

    @staticmethod
    async def delete_llm(user_sub: str, llm_id: str) -> str:
        """
        删除大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型ID
        """
        if llm_id == "empty":
            err = "[LLMManager] 不能删除默认大模型"
            logger.error(err)
            raise ValueError(err)

        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        conv_collection = mongo.get_collection("conversation")

        conv_dict = await conv_collection.find_one({"llm.llm_id": llm_id, "user_sub": user_sub})
        if conv_dict:
            await conv_collection.update_many(
                {"_id": conv_dict["_id"], "user_sub": user_sub},
                {"$set": {"llm": {
                    "llm_id": "empty",
                    "icon": llm_provider_dict["ollama"]["icon"],
                    "model_name": Config().get_config().llm.model,
                }}},
            )

        llm_config = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
        if not llm_config:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        await llm_collection.delete_one({"_id": llm_id, "user_sub": user_sub})
        return llm_id

    @staticmethod
    async def update_conversation_llm(
        user_sub: str,
        conversation_id: str,
        llm_id: str,
    ) -> str:
        """更新对话的LLM"""
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        llm_collection = mongo.get_collection("llm")

        if llm_id != "empty":
            llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)
            llm_dict = {
                "llm_id": llm_dict["_id"],
                "model_name": llm_dict["model_name"],
                "icon": llm_dict["icon"],
            }
        else:
            llm_dict = {
                "llm_id": "empty",
                "model_name": Config().get_config().llm.model,
                "icon": llm_provider_dict["ollama"]["icon"],
            }
        conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not conv_dict:
            err_msg = "[LLMManager] 更新对话的LLM失败，未找到对话"
            logger.error(err_msg)
            raise ValueError(err_msg)

        llm_item = LLMItem(
            llm_id=llm_id,
            model_name=llm_dict["model_name"],
            icon=llm_dict["icon"],
        )
        await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": {"llm": llm_item.model_dump(by_alias=True)}},
        )
        return conversation_id
