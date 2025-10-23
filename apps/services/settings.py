# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""全局设置 Manager"""

import asyncio
import logging

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.llm import embedding
from apps.models import GlobalSettings, LLMType
from apps.scheduler.pool.pool import pool
from apps.schemas.request_data import UpdateSpecialLlmReq
from apps.schemas.response_data import SelectedSpecialLlmID
from apps.services.llm import LLMManager

logger = logging.getLogger(__name__)


class SettingsManager:
    """全局设置相关操作"""

    @staticmethod
    async def get_global_llm_settings() -> SelectedSpecialLlmID:
        """
        获取全局LLM设置

        :return: 全局设置中的functionLLM和embeddingLLM
        """
        async with postgres.session() as session:
            # 查询全局设置表，假设只有一条记录
            settings = (await session.scalars(
                select(GlobalSettings),
            )).first()

            if not settings:
                logger.warning("[SettingsManager] 全局设置不存在，返回默认值")
                return SelectedSpecialLlmID(functionLLM=None, embeddingLLM=None)

            return SelectedSpecialLlmID(
                functionLLM=settings.functionLlmId,
                embeddingLLM=settings.embeddingLlmId,
            )


    @staticmethod
    async def _trigger_vectorization(embedding_llm_id: str) -> None:
        """
        触发向量化过程（后台任务）

        :param embedding_llm_id: Embedding模型ID
        """
        try:
            # 获取新的embedding模型配置
            embedding_llm_config = await LLMManager.get_llm(embedding_llm_id)
            if embedding_llm_config:
                # 设置全局embedding配置
                await embedding.init(embedding_llm_config)

                # 触发向量化
                await pool.set_vector(embedding)

                logger.info("[SettingsManager] Embedding模型已更新，向量化过程已完成")
            else:
                logger.error("[SettingsManager] 选择的embedding模型 %s 不存在", embedding_llm_id)
        except Exception:
            logger.exception("[SettingsManager] Embedding模型向量化过程失败")


    @staticmethod
    async def update_global_llm_settings(
        user_sub: str,
        req: UpdateSpecialLlmReq,
    ) -> None:
        """
        更新全局默认LLM（仅管理员）

        :param user_sub: 操作的管理员user_sub
        :param req: 更新请求体
        """
        # 验证functionLLM是否支持Function Call
        if req.functionLLM:
            function_llm = await LLMManager.get_llm(req.functionLLM)
            if not function_llm:
                err = f"[SettingsManager] Function LLM {req.functionLLM} 不存在"
                raise ValueError(err)
            if LLMType.FUNCTION not in function_llm.llmType:
                err = f"[SettingsManager] LLM {req.functionLLM} 不支持Function Call"
                raise ValueError(err)

        # 验证embeddingLLM是否支持Embedding
        if req.embeddingLLM:
            embedding_llm = await LLMManager.get_llm(req.embeddingLLM)
            if not embedding_llm:
                err = f"[SettingsManager] Embedding LLM {req.embeddingLLM} 不存在"
                raise ValueError(err)
            if LLMType.EMBEDDING not in embedding_llm.llmType:
                err = f"[SettingsManager] LLM {req.embeddingLLM} 不支持Embedding"
                raise ValueError(err)

        # 读取旧的embedding配置
        old_embedding_llm = None
        async with postgres.session() as session:
            settings = (await session.scalars(select(GlobalSettings))).first()
            if settings:
                old_embedding_llm = settings.embeddingLlmId
            else:
                # 如果不存在设置记录，创建一条新记录
                settings = GlobalSettings(
                    functionLlmId=None,
                    embeddingLlmId=None,
                    lastEditedBy=None,
                )
                session.add(settings)

            # 更新全局设置
            settings.functionLlmId = req.functionLLM
            settings.embeddingLlmId = req.embeddingLLM
            settings.lastEditedBy = user_sub
            await session.commit()

        # 如果embedding模型发生变化，在新协程中触发向量化过程
        if old_embedding_llm != req.embeddingLLM and req.embeddingLLM:
            task = asyncio.create_task(SettingsManager._trigger_vectorization(req.embeddingLLM))
            # 添加任务完成回调，避免未处理的异常
            task.add_done_callback(lambda _: None)
            logger.info("[SettingsManager] 已启动后台向量化任务")
