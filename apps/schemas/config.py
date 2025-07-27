# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置文件数据结构"""

from typing import Literal

from pydantic import BaseModel, Field


class NoauthConfig(BaseModel):
    """无认证配置"""

    enable: bool = Field(description="是否启用无认证访问", default=False)
    user_sub: str = Field(description="调试用户的sub", default="admin")


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

    provider: Literal["authhub", "openeuler", "disable"] = Field(description="OIDC Provider", default="authhub")
    settings: OIDCConfig | FixedUserConfig = Field(description="OIDC 配置")


class EmbeddingConfig(BaseModel):
    """Embedding配置"""

    type: str = Field(description="Embedding接口类型", default="openai")
    endpoint: str = Field(description="Embedding模型地址")
    api_key: str = Field(description="Embedding模型API Key")
    model: str = Field(description="Embedding模型名称")


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


class MongoDBConfig(BaseModel):
    """MongoDB配置"""

    host: str = Field(description="MongoDB主机名")
    port: int = Field(description="MongoDB端口号", default=27017)
    user: str = Field(description="MongoDB用户名")
    password: str = Field(description="MongoDB密码")
    database: str = Field(description="MongoDB数据库名")


class LLMConfig(BaseModel):
    """LLM配置"""

    key: str = Field(description="LLM API密钥")
    endpoint: str = Field(description="LLM API URL地址")
    model: str = Field(description="LLM API 模型名")
    max_tokens: int | None = Field(description="LLM API 最大Token数", default=None)
    temperature: float | None = Field(description="LLM API 温度", default=None)


class FunctionCallConfig(BaseModel):
    """Function Call配置"""

    backend: str = Field(description="Function Call 后端")
    model: str = Field(description="Function Call 模型名")
    endpoint: str = Field(description="Function Call API URL地址")
    api_key: str = Field(description="Function Call API密钥")
    max_tokens: int | None = Field(description="Function Call 最大Token数", default=None)
    temperature: float | None = Field(description="Function Call 温度", default=None)


class SecurityConfig(BaseModel):
    """安全配置"""

    half_key1: str = Field(description="Half key 1")
    half_key2: str = Field(description="Half key 2")
    half_key3: str = Field(description="Half key 3")
    jwt_key: str = Field(description="JWT key")


class CheckConfig(BaseModel):
    """敏感词检测配置"""

    enable: bool = Field(description="是否启用敏感词检测")
    words_list: str = Field(description="敏感词列表文件路径")


class ExtraConfig(BaseModel):
    """额外配置"""

    sql_url: str = Field(description="SQL API URL")


class ConfigModel(BaseModel):
    """配置文件的校验Class"""
    no_auth: NoauthConfig = Field(description="无认证配置", default=NoauthConfig())
    deploy: DeployConfig
    login: LoginConfig
    embedding: EmbeddingConfig
    rag: RAGConfig
    fastapi: FastAPIConfig
    minio: MinioConfig
    mongodb: MongoDBConfig
    llm: LLMConfig
    function_call: FunctionCallConfig
    security: SecurityConfig
    check: CheckConfig
    extra: ExtraConfig
