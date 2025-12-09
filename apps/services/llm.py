# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.models import GlobalSettings, LLMData
from apps.schemas.request_data import UpdateLLMReq
from apps.schemas.response_data import (
    LLMAdminInfo,
    LLMProviderInfo,
)

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

    @staticmethod
    async def get_llm(llm_id: str) -> LLMData | None:
        """
        通过ID获取大模型

        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    LLMData.id == llm_id,
                ),
            )).one_or_none()
            if not llm:
                logger.error("[LLMManager] LLM %s 不存在", llm_id)
                return None
            return llm


    @staticmethod
    async def list_llm(llm_id: str | None, *, admin_view: bool = False) -> list[LLMProviderInfo] | list[LLMAdminInfo]:
        """
        获取大模型列表

        :param llm_id: 大模型ID
        :param admin_view: 是否返回管理员视图，True返回LLMAdminInfo，False返回LLMProviderInfo
        :return: 大模型列表
        """
        async with postgres.session() as session:
            if llm_id:
                llm_list = (await session.scalars(
                    select(LLMData).where(
                        LLMData.id == llm_id,
                    ),
                )).all()
            else:
                llm_list = (await session.scalars(
                    select(LLMData),
                )).all()
            if not llm_list:
                logger.error("[LLMManager] 无法找到大模型 %s", llm_id)
                return []

        # 根据admin_view参数返回不同的数据结构
        if admin_view:
            # 构建管理员视图列表
            admin_list = []
            for llm in llm_list:
                llm_item = LLMAdminInfo(
                    llmId=llm.id,
                    llmDescription=llm.llmDescription,
                    llmType=llm.llmType,
                    baseUrl=llm.baseUrl,
                    apiKey=llm.apiKey,
                    modelName=llm.modelName,
                    maxTokens=llm.maxToken,
                    ctxLength=llm.ctxLength,
                    temperature=llm.temperature,
                    provider=llm.provider.value if llm.provider else None,
                    extraConfig=llm.extraConfig,
                )
                admin_list.append(llm_item)
            return admin_list

        # 构建普通用户视图列表
        provider_list = []
        for llm in llm_list:
            llm_item = LLMProviderInfo(
                llmId=llm.id,
                llmDescription=llm.llmDescription,
                llmType=llm.llmType,
                modelName=llm.modelName,
                maxTokens=llm.maxToken,
            )
            provider_list.append(llm_item)
        return provider_list


    @staticmethod
    async def update_llm(llm_id: str, req: UpdateLLMReq) -> str:
        """
        创建或更新大模型

        :param llm_id: 大模型ID
        :param req: 创建或更新大模型请求体
        :return: 大模型ID
        """
        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    LLMData.id == llm_id,
                ),
            )).one_or_none()

            if llm:
                # 更新现有条目
                llm.baseUrl = req.base_url
                llm.apiKey = req.api_key
                llm.modelName = req.model_name
                llm.maxToken = req.max_tokens
                llm.provider = req.provider
                llm.ctxLength = req.ctx_length
                llm.llmDescription = req.llm_description
                if req.llm_type is not None:
                    llm.llmType = req.llm_type
                llm.extraConfig = req.extra_data or {}
            else:
                # 创建新条目
                llm_data = {
                    "id": llm_id,
                    "baseUrl": req.base_url,
                    "apiKey": req.api_key,
                    "modelName": req.model_name,
                    "maxToken": req.max_tokens,
                    "provider": req.provider,
                    "ctxLength": req.ctx_length,
                    "llmDescription": req.llm_description,
                    "llmType": req.llm_type or [],
                    "extraConfig": req.extra_data or {},
                }
                llm = LLMData(**llm_data)
                session.add(llm)

            await session.commit()
            return llm.id


    @staticmethod
    async def delete_llm(llm_id: str) -> None:
        """
        删除大模型

        :param llm_id: 大模型ID
        """
        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    LLMData.id == llm_id,
                ),
            )).one_or_none()
            if not llm:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                raise ValueError(err)
            await session.delete(llm)
            await session.commit()

        async with postgres.session() as session:
            # 清除GlobalSettings中的引用
            global_settings = (await session.scalars(
                select(GlobalSettings),
            )).all()
            for settings in global_settings:
                if settings.functionLlmId == llm_id:
                    settings.functionLlmId = None
                if settings.embeddingLlmId == llm_id:
                    settings.embeddingLlmId = None
            await session.commit()
