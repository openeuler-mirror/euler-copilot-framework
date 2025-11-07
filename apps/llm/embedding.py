# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Embedding模型"""

import logging
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

from apps.common.postgres import postgres
from apps.models import Base, LLMData, LLMProvider

from .providers import BaseProvider, OpenAIProvider, TEIProvider

_logger = logging.getLogger(__name__)

_CLASS_DICT: dict[LLMProvider, type[BaseProvider]] = {
    LLMProvider.OPENAI: OpenAIProvider,
    LLMProvider.TEI: TEIProvider,
}


class VectorBase(DeclarativeBase):
    """向量表基类，共享主应用Base的metadata"""

    metadata = Base.metadata


class VectorTableManager:
    """向量表管理器"""

    _current_dim: int | None = None
    _current_model_fingerprint: str | None = None
    _tables_created: bool = False

    VectorBase: Any = None
    NodePoolVector: Any = None
    FlowPoolVector: Any = None
    ServicePoolVector: Any = None
    MCPVector: Any = None
    MCPToolVector: Any = None

    async def _get_table_metadata(self) -> tuple[bool, int | None, str | None]:
        """从数据库读取表的元数据（维度和模型指纹）"""
        async with postgres.session() as session:
            try:
                # 首先尝试从表的默认值定义中获取维度和模型指纹
                result = await session.execute(
                    text(
                        "SELECT "
                        "  pg_get_expr(adbin, adrelid) as default_value, "
                        "  attname "
                        "FROM pg_attribute "
                        "JOIN pg_attrdef ON adrelid = attrelid AND adnum = attnum "
                        "WHERE attrelid = 'framework_flow_vector'::regclass "
                        "  AND attname IN ('embedding', 'model_fingerprint')",
                    ),
                )
                rows = result.all()

                existing_dim = None
                existing_fingerprint = None

                for row in rows:
                    if row[1] == "embedding":
                        # 从默认值字符串 '[0,0,0,...]'::vector 中提取维度
                        default_str = row[0]
                        if default_str and default_str.startswith("'["):
                            # 计算逗号数量+1得到维度
                            vector_str = default_str.split("'")[1]  # 提取 '[0,0,0,...]'
                            existing_dim = vector_str.count(",") + 1
                    elif row[1] == "model_fingerprint":
                        # 从默认值字符串中提取模型指纹
                        default_str = row[0]
                        if default_str and default_str.startswith("'"):
                            existing_fingerprint = default_str.strip("'").split("'")[0]

                if existing_dim is not None:
                    return True, existing_dim, existing_fingerprint
            except Exception as e:  # noqa: BLE001
                _logger.debug("[VectorTableManager] 无法读取表元数据: %s", e)
        return False, None, None

    async def ensure_tables(self, dim: int, llm_config: LLMData) -> None:
        """确保向量表存在且维度和模型都正确"""
        if dim <= 0:
            err = "[VectorTableManager] 检测到的Embedding维度为0，无法创建Vector表"
            _logger.error(err)
            raise RuntimeError(err)

        model_fingerprint = llm_config.modelName or ""

        table_exists, existing_dim, existing_fingerprint = await self._get_table_metadata()

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
            needs_rebuild = True
            rebuild_reason = "表中无数据或缺少模型指纹"
            _logger.warning("[VectorTableManager] %s", rebuild_reason)

        if not needs_rebuild:
            _logger.debug(
                "[VectorTableManager] 向量表已存在且有效，维度=%d，模型=%s/%s，指纹=%s",
                dim,
                llm_config.provider,
                llm_config.modelName,
                model_fingerprint,
            )
            # 即使表已存在，也需要定义ORM类以便后续使用
            self._define_orm_classes(dim, llm_config)
            self._current_dim = dim
            self._current_model_fingerprint = model_fingerprint
            self._tables_created = True
            return

        _logger.warning("[VectorTableManager] 将删除旧表并重建。原因: %s", rebuild_reason)

        if table_exists:
            await self._drop_tables()

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

    def _define_orm_classes(self, dim: int, llm_config: LLMData) -> None:
        """定义ORM类，关联到数据库表"""
        self.VectorBase = VectorBase
        model_fingerprint = llm_config.modelName or ""
        # 创建dim长度的全零向量作为默认值
        zero_vector = "[" + ",".join(["0"] * dim) + "]"

        flow_pool_table_def = {
            "__tablename__": "framework_flow_vector",
            "appId": Column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False),
            "id": Column(String(255), ForeignKey("framework_flow.id"), primary_key=True),
            "embedding": Column(Vector(dim), nullable=False, server_default=zero_vector),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "flow_vector_hnsw_index",
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
            "embedding": Column(Vector(dim), nullable=False, server_default=zero_vector),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "service_vector_hnsw_index",
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
            "embedding": Column(Vector(dim), nullable=False, server_default=zero_vector),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "node_vector_hnsw_index",
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
            "embedding": Column(Vector(dim), nullable=False, server_default=zero_vector),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "mcp_vector_hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        mcp_tool_table_def = {
            "__tablename__": "framework_mcp_tool_vector",
            "id": Column(BigInteger, ForeignKey("framework_mcp_tools.id"), primary_key=True),
            "mcpId": Column(String(255), ForeignKey("framework_mcp.id"), nullable=False),
            "embedding": Column(Vector(dim), nullable=False, server_default=zero_vector),
            "model_fingerprint": Column(String(300), nullable=False, server_default=model_fingerprint),
            "__table_args__": (
                Index(
                    "mcp_tool_vector_hnsw_index",
                    "embedding",
                    postgresql_using="hnsw",
                    postgresql_with={"m": 16, "ef_construction": 200},
                    postgresql_ops={"embedding": "vector_cosine_ops"},
                ),
            ),
        }

        self.FlowPoolVector = type("FlowPoolVector", (self.VectorBase,), flow_pool_table_def)
        self.ServicePoolVector = type("ServicePoolVector", (self.VectorBase,), service_pool_table_def)
        self.NodePoolVector = type("NodePoolVector", (self.VectorBase,), node_pool_table_def)
        self.MCPVector = type("MCPVector", (self.VectorBase,), mcp_table_def)
        self.MCPToolVector = type("MCPToolVector", (self.VectorBase,), mcp_tool_table_def)

    async def _create_tables(self, dim: int, llm_config: LLMData) -> None:
        """创建向量表"""
        # 首先定义ORM类
        self._define_orm_classes(dim, llm_config)

        # 然后在事务中执行create_all创建实际的数据库表
        async with postgres.engine.begin() as conn:
            await conn.run_sync(self.VectorBase.metadata.create_all)


vector_table_manager = VectorTableManager()


class Embedding:
    """Embedding模型"""

    _table_manager = vector_table_manager
    _llm_config: LLMData | None = None
    _provider: BaseProvider | None = None

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
        """初始化Embedding配置和资源"""
        if llm_config is None:
            err = "[Embedding] 未设置LLM配置"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[Embedding] 初始化Embedding，模型=%s/%s", llm_config.provider, llm_config.modelName)
        self._llm_config = llm_config
        self._provider = _CLASS_DICT[llm_config.provider](llm_config)

        dim = await self._get_embedding_dimension()
        _logger.info("[Embedding] 检测到向量维度: %d", dim)

        await self._table_manager.ensure_tables(dim, self._llm_config)
        _logger.info("[Embedding] 向量表检查完成")

    async def get_embedding(self, text: list[str]) -> list[list[float]]:
        """获取文本的向量表示"""
        if not self._provider:
            err = "[Embedding] Provider未初始化，无法获取embedding"
            _logger.error(err)
            raise RuntimeError(err)
        return await self._provider.embedding(text)


embedding = Embedding()
