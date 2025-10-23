# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Embedding模型"""

import asyncio
import logging
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

from apps.common.postgres import postgres
from apps.models import LLMData, LLMProvider

from .providers import BaseProvider, OpenAIProvider, TEIProvider

_logger = logging.getLogger(__name__)

# Provider类型映射
_CLASS_DICT: dict[LLMProvider, type[BaseProvider]] = {
    LLMProvider.OPENAI: OpenAIProvider,
    LLMProvider.TEI: TEIProvider,
}


class VectorTableManager:
    """
    向量表管理器（单例模式）

    负责管理所有向量表的创建、删除和维度变更。
    使用单例模式确保全局只有一个实例，避免并发问题。

    核心功能：
    - 跟踪当前使用的 embedding 模型指纹
    - 检测模型变化（不仅是维度，还有模型本身）
    - 自动重建表以避免向量空间不匹配
    """

    _instance: "VectorTableManager | None" = None
    _current_dim: int | None = None
    _current_model_fingerprint: str | None = None  # 当前模型指纹
    _tables_created: bool = False
    _lock: asyncio.Lock = asyncio.Lock()

    # 类属性：存储当前的表类定义
    VectorBase: Any = None
    NodePoolVector: Any = None
    FlowPoolVector: Any = None
    ServicePoolVector: Any = None
    MCPVector: Any = None
    MCPToolVector: Any = None

    def __new__(cls) -> "VectorTableManager":
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _get_table_metadata(self) -> tuple[bool, int | None, str | None]:
        """
        从数据库中读取表的元数据（维度和模型指纹）

        :return: (表是否存在, 维度, 模型指纹)
        """
        async with postgres.session() as session:
            try:
                # 查询表结构和数据
                result = await session.execute(
                    text(
                        "SELECT "
                        "  (SELECT atttypmod FROM pg_attribute "
                        "   WHERE attrelid = 'framework_flow_vector'::regclass AND attname = 'embedding') as dim_raw, "
                        "  (SELECT model_fingerprint FROM framework_flow_vector LIMIT 1) as fingerprint",
                    ),
                )
                row = result.first()
                if row and row[0] is not None:
                    # pgvector 的 atttypmod 编码：实际维度 + 4
                    existing_dim = row[0] - 4 if row[0] > 0 else 0
                    existing_fingerprint = row[1]  # 可能为 None（表为空）
                    return True, existing_dim, existing_fingerprint
            except Exception:  # noqa: BLE001
                # 表不存在会抛出异常
                return False, None, None
            else:
                # 表存在但无数据或字段不存在
                return False, None, None

    async def ensure_tables(self, dim: int, llm_config: LLMData) -> None:
        """
        确保向量表存在且维度和模型都正确

        检查：
        1. 表是否存在（从数据库查询，支持重启恢复）
        2. 维度是否匹配
        3. 模型指纹是否匹配（同维度但不同模型也需要重建）

        :param dim: 向量维度
        :param llm_config: LLM配置（用于获取模型名称作为指纹）
        :raises RuntimeError: 当维度无效时
        """
        if dim <= 0:
            err = "[VectorTableManager] 检测到的Embedding维度为0，无法创建Vector表"
            _logger.error(err)
            raise RuntimeError(err)

        # 使用模型名称作为指纹
        model_fingerprint = llm_config.modelName

        async with self._lock:
            # 从数据库读取现有表的元数据（支持重启恢复）
            table_exists, existing_dim, existing_fingerprint = await self._get_table_metadata()

            # 检查是否需要重建表
            needs_rebuild = False
            rebuild_reason = ""

            if not table_exists:
                needs_rebuild = True
                rebuild_reason = "表不存在"
                _logger.info("[VectorTableManager] 数据库中不存在向量表，将创建新表")
            elif existing_dim != dim:
                needs_rebuild = True
                rebuild_reason = f"维度不匹配：数据库={existing_dim}, 需要={dim}"
                _logger.warning("[VectorTableManager] %s", rebuild_reason)
            elif existing_fingerprint and existing_fingerprint != model_fingerprint:
                needs_rebuild = True
                rebuild_reason = (
                    f"模型变化：{llm_config.provider}/{llm_config.modelName} "
                    f"(数据库指纹={existing_fingerprint}, 当前指纹={model_fingerprint})"
                )
                _logger.warning("[VectorTableManager] %s", rebuild_reason)
            elif not existing_fingerprint:
                # 表存在但没有数据（或旧版本没有指纹列），保守起见重建
                needs_rebuild = True
                rebuild_reason = "表中无数据或缺少模型指纹，重建以确保一致性"
                _logger.warning("[VectorTableManager] %s", rebuild_reason)

            # 如果不需要重建，直接返回
            if not needs_rebuild:
                _logger.debug(
                    "[VectorTableManager] 向量表已存在且有效，维度=%d，模型=%s/%s，指纹=%s",
                    dim,
                    llm_config.provider,
                    llm_config.modelName,
                    model_fingerprint,
                )
                # 更新内存状态（重启后恢复）
                self._current_dim = dim
                self._current_model_fingerprint = model_fingerprint
                self._tables_created = True
                return

            # 需要重建
            _logger.warning("[VectorTableManager] 将删除旧表并重建。原因: %s", rebuild_reason)

            # 如果表已存在，先删除
            if table_exists:
                await self._drop_tables()

            # 创建新表
            _logger.info(
                "[VectorTableManager] 开始创建向量表，维度=%d，模型=%s/%s，指纹=%s",
                dim,
                llm_config.provider,
                llm_config.modelName,
                model_fingerprint,
            )
            await self._create_tables(dim, llm_config)
            self._current_dim = dim
            self._current_model_fingerprint = model_fingerprint
            self._tables_created = True
            _logger.info("[VectorTableManager] 向量表创建成功")

    async def _drop_tables(self) -> None:
        """删除所有向量表"""
        _logger.info("[VectorTableManager] 删除所有向量表")
        async with postgres.session() as session:
            await session.execute(text("DROP TABLE IF EXISTS framework_flow_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_service_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_node_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_mcp_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_mcp_tool_vector"))
            await session.commit()
        self._tables_created = False

    async def _create_tables(self, dim: int, llm_config: LLMData) -> None:
        """
        创建向量表

        :param dim: 向量维度
        :param llm_config: LLM配置（用于获取模型名称作为指纹）
        """
        # 创建新的 Base（避免污染全局状态）
        self.VectorBase = declarative_base()

        # 使用模型名称作为指纹
        model_fingerprint = llm_config.modelName

        # 定义表结构（使用局部变量，不污染全局字典）
        flow_pool_table_def = {
            "__tablename__": "framework_flow_vector",
            "appId": Column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False),
            "id": Column(String(255), ForeignKey("framework_flow.id"), primary_key=True),
            "embedding": Column(Vector(dim), nullable=False),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        service_pool_table_def = {
            "__tablename__": "framework_service_vector",
            "id": Column(UUID(as_uuid=True), ForeignKey("framework_service.id"), primary_key=True),
            "embedding": Column(Vector(dim), nullable=False),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        node_pool_table_def = {
            "__tablename__": "framework_node_vector",
            "id": Column(String(255), ForeignKey("framework_node.id"), primary_key=True),
            "serviceId": Column(UUID(as_uuid=True), ForeignKey("framework_service.id"), nullable=True),
            "embedding": Column(Vector(dim), nullable=False),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        mcp_table_def = {
            "__tablename__": "framework_mcp_vector",
            "id": Column(String(255), ForeignKey("framework_mcp.id"), primary_key=True),
            "embedding": Column(Vector(dim), nullable=False),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        mcp_tool_table_def = {
            "__tablename__": "framework_mcp_tool_vector",
            "id": Column(String(255), ForeignKey("framework_mcp_tool.id"), primary_key=True),
            "mcpId": Column(String(255), ForeignKey("framework_mcp.id"), nullable=False),
            "embedding": Column(Vector(dim), nullable=False),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        # 动态创建表类
        self.FlowPoolVector = type("FlowPoolVector", (self.VectorBase,), flow_pool_table_def)
        self.ServicePoolVector = type("ServicePoolVector", (self.VectorBase,), service_pool_table_def)
        self.NodePoolVector = type("NodePoolVector", (self.VectorBase,), node_pool_table_def)
        self.MCPVector = type("MCPVector", (self.VectorBase,), mcp_table_def)
        self.MCPToolVector = type("MCPToolVector", (self.VectorBase,), mcp_tool_table_def)

        # 创建表
        self.VectorBase.metadata.create_all(postgres.engine)


class Embedding:
    """Embedding模型"""

    # 使用全局单例的 VectorTableManager
    _table_manager = VectorTableManager()
    _llm_config: LLMData | None = None
    _provider: BaseProvider | None = None

    # 便捷访问属性（指向 VectorTableManager 的表类）
    @property
    def VectorBase(self) -> Any:  # noqa: N802
        """获取VectorBase"""
        return self._table_manager.VectorBase

    @property
    def NodePoolVector(self) -> Any:  # noqa: N802
        """获取NodePoolVector"""
        return self._table_manager.NodePoolVector

    @property
    def FlowPoolVector(self) -> Any:  # noqa: N802
        """获取FlowPoolVector"""
        return self._table_manager.FlowPoolVector

    @property
    def ServicePoolVector(self) -> Any:  # noqa: N802
        """获取ServicePoolVector"""
        return self._table_manager.ServicePoolVector

    @property
    def MCPVector(self) -> Any:  # noqa: N802
        """获取MCPVector"""
        return self._table_manager.MCPVector

    @property
    def MCPToolVector(self) -> Any:  # noqa: N802
        """获取MCPToolVector"""
        return self._table_manager.MCPToolVector

    async def _get_embedding_dimension(self) -> int:
        """获取Embedding的维度"""
        embedding = await self.get_embedding(["测试文本"])
        return len(embedding[0])

    async def init(self, llm_config: LLMData | None) -> None:
        """
        初始化Embedding配置和资源

        设置LLM配置，检测向量维度，并确保数据库向量表存在且维度正确。
        如果模型或维度发生变化，会自动删除旧表并重建。

        :param llm_config: LLM配置
        :raises RuntimeError: 当llm_config为None时抛出
        """
        if llm_config is None:
            err = "[Embedding] 未设置LLM配置"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[Embedding] 初始化Embedding，模型=%s/%s", llm_config.provider, llm_config.modelName)
        self._llm_config = llm_config
        self._provider = _CLASS_DICT[llm_config.provider](llm_config)

        # 检测维度
        dim = await self._get_embedding_dimension()
        _logger.info("[Embedding] 检测到向量维度: %d", dim)

        # 使用 VectorTableManager 确保表存在且维度和模型都正确
        await self._table_manager.ensure_tables(dim, self._llm_config)
        _logger.info("[Embedding] 向量表检查完成")

    async def get_embedding(self, text: list[str]) -> list[list[float]]:
        """
        访问OpenAI兼容的Embedding API，获得向量化数据

        :param text: 待向量化文本（多条文本组成List）
        :return: 文本对应的向量（顺序与text一致，也为List）
        """
        if not self._provider:
            err = "[Embedding] Provider未初始化，无法获取embedding"
            _logger.error(err)
            raise RuntimeError(err)
        return await self._provider.embedding(text)


# 全局Embedding实例
embedding = Embedding()
