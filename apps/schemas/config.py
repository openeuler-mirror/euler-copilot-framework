# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置文件数据结构"""

from pydantic import BaseModel, Field


class DeployConfig(BaseModel):
    """部署配置"""

    mode: str = Field(description="部署方式", default="local")
    cookie: str = Field(description="COOKIE SET 方式", default="domain")
    data_dir: str = Field(description="数据存储路径")


class RAGConfig(BaseModel):
    """RAG配置"""

    rag_service: str = Field(description="RAG服务地址")


class FastAPIConfig(BaseModel):
    """FastAPI配置"""

    domain: str = Field(description="当前实例的域名")


class PostgresConfig(BaseModel):
    """Postgres配置"""

    host: str = Field(description="Postgres主机名")
    port: int = Field(description="Postgres端口号", default=5432)
    user: str = Field(description="Postgres用户名")
    password: str = Field(description="Postgres密码")
    database: str = Field(description="Postgres数据库名")


class SecurityConfig(BaseModel):
    """安全配置"""

    half_key1: str = Field(description="Half key 1")
    half_key2: str = Field(description="Half key 2")
    half_key3: str = Field(description="Half key 3")
    jwt_key: str = Field(description="JWT key")


class ExtraConfig(BaseModel):
    """额外配置"""

    sql_url: str = Field(description="SQL API URL")


class ConfigModel(BaseModel):
    """配置文件的校验Class"""

    deploy: DeployConfig
    rag: RAGConfig
    fastapi: FastAPIConfig
    postgres: PostgresConfig
    security: SecurityConfig
    extra: ExtraConfig
