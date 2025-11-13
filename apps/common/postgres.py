# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import Index
import urllib.parse
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, func
from sqlalchemy.orm import declarative_base
from apps.common.config import Config
Base = declarative_base()


class FlowPoolVector(Base):
    """App向量信息"""

    __tablename__ = "flow_pool_vector"

    id = Column(String, primary_key=True, index=True)
    app_id = Column(String, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]

    __table_args__ = (
        Index(
            'ix_flow_pool_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class ServicePoolVector(Base):
    """Service向量信息"""

    __tablename__ = "service_pool_vector"

    id = Column(String, primary_key=True, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]

    __table_args__ = (
        Index(
            'ix_service_pool_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class CallPoolVector(Base):
    """Call向量信息"""

    __tablename__ = "call_pool_vector"

    id = Column(String, primary_key=True, index=True)
    service_id = Column(String, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]

    __table_args__ = (
        Index(
            'ix_call_pool_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class NodePoolVector(Base):
    """Node向量信息"""

    __tablename__ = "node_pool_vector"

    id = Column(String, primary_key=True, index=True)
    service_id = Column(String, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]

    __table_args__ = (
        Index(
            'ix_node_pool_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class McpVector(Base):
    """MCP向量化数据，存储在LanceDB的 ``mcp`` 表中"""

    __tablename__ = "mcp_vector"

    id = Column(String, primary_key=True, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]
    __table_args__ = (
        Index(
            'ix_mcp_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class McpToolVector(Base):
    """MCP工具向量化数据，存储在LanceDB的 ``mcp_tool`` 表中"""

    __tablename__ = "mcp_tool_vector"

    id = Column(String, primary_key=True, index=True)
    mcp_id = Column(String, index=True)
    embedding = Column(Vector(dim=1024))  # type: ignore[call-arg]
    __table_args__ = (
        Index(
            'ix_mcp_tool_vector_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 200},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )


class DataBase:

    # 对密码进行 URL 编码
    user = Config().get_config().vectordb.user
    host = Config().get_config().vectordb.host
    port = Config().get_config().vectordb.port
    password = Config().get_config().vectordb.password
    db = Config().get_config().vectordb.db
    encoded_password = urllib.parse.quote_plus(password)

    if Config().get_config().vectordb.type == 'opengauss':
        database_url = f"opengauss+asyncpg://{user}:{encoded_password}@{host}:{port}/{db}"
    else:
        database_url = f"postgresql+asyncpg://{user}:{encoded_password}@{host}:{port}/{db}"
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_recycle=300,
        pool_pre_ping=True
    )
    init_all_table_flag = False

    @classmethod
    async def init(cls) -> None:
        """初始化数据库连接"""
        if Config().get_config().vectordb.type == 'opengauss':
            from sqlalchemy import event
            from opengauss_sqlalchemy.register_async import register_vector

            @event.listens_for(DataBase.engine.sync_engine, "connect")
            def connect(dbapi_connection, connection_record):
                dbapi_connection.run_async(register_vector)
        async with DataBase.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    async def get_session(cls):
        if DataBase.init_all_table_flag is False:
            await DataBase.init()
            DataBase.init_all_table_flag = True
        connection = async_sessionmaker(
            DataBase.engine, expire_on_commit=False)()
        return cls._ConnectionManager(connection)

    class _ConnectionManager:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self.connection.close()
