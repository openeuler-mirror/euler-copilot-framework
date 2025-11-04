# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""全局设置 Manager"""

import asyncio
import logging

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.llm import LLM, embedding, json_generator
from apps.models import GlobalSettings, LLMType
from apps.scheduler.pool.pool import pool
from apps.schemas.request_data import UpdateSpecialLlmReq
from apps.schemas.response_data import SelectedSpecialLlmID
from apps.services.llm import LLMManager

_logger = logging.getLogger(__name__)


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
                _logger.warning("[SettingsManager] 全局设置不存在，返回默认值")
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
                await pool.set_vector()

                _logger.info("[SettingsManager] Embedding模型已更新，向量化过程已完成")
            else:
                _logger.error("[SettingsManager] 选择的embedding模型 %s 不存在", embedding_llm_id)
        except Exception:
            _logger.exception("[SettingsManager] Embedding模型向量化过程失败")


    @staticmethod
    async def _initialize_function_llm(function_llm_id: str) -> None:
        """
        初始化Function LLM

        :param function_llm_id: Function LLM ID
        :raises ValueError: 如果LLM不存在或不支持Function Call
        """
        function_llm = await LLMManager.get_llm(function_llm_id)
        if not function_llm:
            err = f"[SettingsManager] Function LLM {function_llm_id} 不存在"
            raise ValueError(err)
        if LLMType.FUNCTION not in function_llm.llmType:
            err = f"[SettingsManager] LLM {function_llm_id} 不支持Function Call"
            raise ValueError(err)

        # 更新json_generator单例
        llm_instance = LLM(function_llm)
        json_generator.init(llm_instance)
        _logger.info("[SettingsManager] Function LLM已初始化，json_generator已配置")


    @staticmethod
    async def _validate_embedding_llm(embedding_llm_id: str) -> None:
        """
        验证Embedding LLM是否有效

        :param embedding_llm_id: Embedding LLM ID
        :raises ValueError: 如果LLM不存在或不支持Embedding
        """
        embedding_llm = await LLMManager.get_llm(embedding_llm_id)
        if not embedding_llm:
            err = f"[SettingsManager] Embedding LLM {embedding_llm_id} 不存在"
            raise ValueError(err)
        if LLMType.EMBEDDING not in embedding_llm.llmType:
            err = f"[SettingsManager] LLM {embedding_llm_id} 不支持Embedding"
            raise ValueError(err)


    @staticmethod
    async def init_global_llm_settings() -> None:
        """
        初始化全局LLM设置（用于项目启动时调用）

        从数据库读取全局设置并初始化对应的LLM实例
        """
        async with postgres.session() as session:
            settings = (await session.scalars(select(GlobalSettings))).first()

            if not settings:
                _logger.warning("[SettingsManager] 全局设置不存在，跳过LLM初始化")
                return

            # 初始化Function LLM
            if settings.functionLlmId:
                try:
                    await SettingsManager._initialize_function_llm(settings.functionLlmId)
                    _logger.info("[SettingsManager] Function LLM初始化完成: %s", settings.functionLlmId)
                except ValueError:
                    _logger.exception("[SettingsManager] Function LLM初始化失败")
            else:
                _logger.info("[SettingsManager] Function LLM未配置，跳过初始化")

            # 初始化Embedding LLM
            if settings.embeddingLlmId:
                try:
                    await SettingsManager._validate_embedding_llm(settings.embeddingLlmId)
                    # 初始化embedding配置
                    embedding_llm_config = await LLMManager.get_llm(settings.embeddingLlmId)
                    if embedding_llm_config:
                        await embedding.init(embedding_llm_config)
                        _logger.info("[SettingsManager] Embedding LLM初始化完成: %s", settings.embeddingLlmId)
                except ValueError:
                    _logger.exception("[SettingsManager] Embedding LLM初始化失败")
            else:
                _logger.info("[SettingsManager] Embedding LLM未配置，跳过初始化")


    @staticmethod
    async def update_global_llm_settings(
        user_id: str,
        req: UpdateSpecialLlmReq,
    ) -> None:
        """
        更新全局默认LLM（仅管理员）

        :param user_id: 操作的管理员user_id
        :param req: 更新请求体
        """
        # 验证并初始化functionLLM
        if req.functionLLM:
            await SettingsManager._initialize_function_llm(req.functionLLM)

        # 验证embeddingLLM
        if req.embeddingLLM:
            await SettingsManager._validate_embedding_llm(req.embeddingLLM)

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
            settings.lastEditedBy = user_id
            await session.commit()

        # 如果embedding模型发生变化，在新协程中触发向量化过程
        if old_embedding_llm != req.embeddingLLM and req.embeddingLLM:
            task = asyncio.create_task(SettingsManager._trigger_vectorization(req.embeddingLLM))
            # 添加任务完成回调，避免未处理的异常
            task.add_done_callback(lambda _: None)
            _logger.info("[SettingsManager] 已启动后台向量化任务")
