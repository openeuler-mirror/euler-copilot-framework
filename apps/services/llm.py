# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.llm import Embedding
from apps.models import LLMData, User
from apps.scheduler.pool.pool import pool
from apps.schemas.request_data import (
    UpdateLLMReq,
    UpdateUserSelectedLLMReq,
)
from apps.schemas.response_data import (
    LLMAdminInfo,
    LLMProviderInfo,
    SelectedSpecialLLMID,
)

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

    @staticmethod
    async def get_llm(llm_id: str) -> LLMData | None:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
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
    async def list_provider(llm_id: str | None) -> list[LLMProviderInfo]:
        """
        获取大模型列表

        :param llm_id: 大模型ID
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

        # 默认大模型
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
    async def list_llm(llm_id: str | None) -> list[LLMAdminInfo]:
        """
        获取大模型数据列表（管理员视图）

        :param llm_id: 大模型ID
        :return: 大模型管理信息列表
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


    @staticmethod
    async def update_llm(llm_id: str, req: UpdateLLMReq) -> str:
        """
        创建大模型

        :param req: 创建大模型请求体
        :return: 大模型对象
        """
        async with postgres.session() as session:
            if llm_id:
                llm = (await session.scalars(
                    select(LLMData).where(
                        LLMData.id == llm_id,
                    ),
                )).one_or_none()
                if not llm:
                    err = f"[LLMManager] LLM {llm_id} 不存在"
                    raise ValueError(err)
                llm.baseUrl = req.base_url
                llm.apiKey = req.api_key
                llm.modelName = req.model_name
                llm.maxToken = req.max_tokens
                llm.provider = req.provider
                llm.ctxLength = req.ctx_length
                llm.llmDescription = req.llm_description
                llm.extraConfig = req.extra_data or {}
                await session.commit()
            else:
                llm = LLMData(
                    id=llm_id,
                    baseUrl=req.base_url,
                    apiKey=req.api_key,
                    modelName=req.model_name,
                    maxToken=req.max_tokens,
                    provider=req.provider,
                    ctxLength=req.ctx_length,
                    llmDescription=req.llm_description,
                    extraConfig=req.extra_data or {},
                )
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
            # 清除所有FunctionLLM的引用
            user = list((await session.scalars(
                select(User).where(User.functionLLM == llm_id),
            )).all())
            for item in user:
                item.functionLLM = None
            # 清除所有EmbeddingLLM的引用
            user = list((await session.scalars(
                select(User).where(User.embeddingLLM == llm_id),
            )).all())
            for item in user:
                item.embeddingLLM = None
            await session.commit()


    @staticmethod
    async def update_special_llm(
        user_sub: str,
        req: UpdateUserSelectedLLMReq,
    ) -> None:
        """更新用户的默认LLM"""
        # 检查embedding模型是否发生变化
        old_embedding_llm = None
        new_embedding_llm = req.embeddingLLM

        async with postgres.session() as session:
            user = (await session.scalars(
                select(User).where(User.userSub == user_sub),
            )).one_or_none()
            if not user:
                err = f"[LLMManager] 用户 {user_sub} 不存在"
                raise ValueError(err)

            old_embedding_llm = user.embeddingLLM
            user.functionLLM = req.functionLLM
            user.embeddingLLM = req.embeddingLLM
            await session.commit()

        # 如果embedding模型发生变化，触发向量化过程
        if old_embedding_llm != new_embedding_llm and new_embedding_llm:
            try:
                # 获取新的embedding模型配置
                embedding_llm_config = await LLMManager.get_llm(new_embedding_llm)
                if embedding_llm_config:
                    # 创建Embedding实例
                    embedding_model = Embedding(embedding_llm_config)
                    await embedding_model.init()

                    # 触发向量化
                    await pool.set_vector(embedding_model)

                    logger.info("[LLMManager] 用户 %s 的embedding模型已更新，向量化过程已完成", user_sub)
                else:
                    logger.error("[LLMManager] 用户 %s 选择的embedding模型 %s 不存在", user_sub, new_embedding_llm)
            except Exception:
                logger.exception("[LLMManager] 用户 %s 的embedding模型向量化过程失败", user_sub)
