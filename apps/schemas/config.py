# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置文件数据结构"""

from typing import Literal

from pydantic import BaseModel, Field


class DeployConfig(BaseModel):
    """部署配置"""

    mode: str = Field(description="部署方式", default="local")
    cookie: str = Field(description="COOKIE SET 方式", default="domain")
    data_dir: str = Field(description="数据存储路径")


class OIDCConfig(BaseModel):
    """AuthHub认证配置"""

    host: str = Field(description="OIDC服务路径")
    host_inner: str = Field(description="OIDC服务路径(内网)")
    login_api: str = Field(description="EulerCopilot登录API")
    app_id: str = Field(description="OIDC AppID")
    app_secret: str = Field(description="OIDC App Secret")


class FixedUserConfig(BaseModel):
    """固定用户配置"""

    user_id: str = Field(description="禁用登录后，默认的用户ID")


class LoginConfig(BaseModel):
    """OIDC配置"""

    provider: Literal[
        "authhub", "openeuler", "authelia", "disable",
    ] = Field(description="OIDC Provider", default="authhub")
    admin_user: list[str] = Field(description="管理员用户ID列表", default=[])
    settings: OIDCConfig | FixedUserConfig = Field(description="OIDC 配置")


class RAGConfig(BaseModel):
    """RAG配置"""

    rag_service: str = Field(description="RAG服务地址")


class FastAPIConfig(BaseModel):
    """FastAPI配置"""

    domain: str = Field(description="当前实例的域名")


class MinioConfig(BaseModel):
    """Minio配置"""

    endpoint: str = Field(description="Minio主机名、端口号")
    access_key: str = Field(description="MinIO访问密钥")
    secret_key: str = Field(description="MinIO密钥")
    secure: bool = Field(description="MinIO是否启用SSL", default=False)


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
    login: LoginConfig
    rag: RAGConfig
    fastapi: FastAPIConfig
    minio: MinioConfig
    postgres: PostgresConfig
    security: SecurityConfig
    extra: ExtraConfig
