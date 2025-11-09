# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置文件数据结构"""

from typing import Literal

from pydantic import BaseModel, Field


class NoauthConfig(BaseModel):
    """无认证配置"""

    enable: bool = Field(description="是否启用无认证访问", default=False)
    user_sub: str = Field(description="无认证模式下的用户标识", default="openEuler")
    user_name: str = Field(description="无认证模式下的用户名", default="openEuler")


class AdminConfig(BaseModel):
    """管理员配置"""
    enable: bool = Field(description="是否启用管理员", default=False)
    user_sub: str = Field(description="管理员用户标识", default="openEuler")
    user_name: str = Field(description="管理员用户名", default="openEuler")


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
    redirect_settings_url: str | None = Field(description="用户设置页面重定向URL", default=None)


class AutheliaConfig(BaseModel):
    """Authelia认证配置"""

    host: str = Field(description="Authelia服务路径")
    client_id: str = Field(description="OIDC Client ID")
    client_secret: str = Field(description="OIDC Client Secret")
    redirect_uri: str = Field(description="重定向URI")
    enable_pkce: bool = Field(description="是否启用PKCE", default=True)
    pkce_challenge_method: str = Field(description="PKCE挑战方法", default="S256")
    redirect_settings_url: str | None = Field(description="用户设置页面重定向URL", default=None)


class OpenEulerConfig(BaseModel):
    """OpenEuler认证配置"""

    host: str = Field(description="OpenEuler服务路径")
    redirect_settings_url: str | None = Field(description="用户设置页面重定向URL", default=None)


class FixedUserConfig(BaseModel):
    """固定用户配置"""

    user_id: str = Field(description="禁用登录后，默认的用户ID")


class LoginConfig(BaseModel):
    """OIDC配置"""

    provider: Literal["authhub", "openeuler", "authelia", "disable"] = Field(
        description="OIDC Provider", default="authhub")
    settings: OIDCConfig | AutheliaConfig | OpenEulerConfig | FixedUserConfig = Field(
        description="OIDC 配置")


class EmbeddingConfig(BaseModel):
    """Embedding配置"""

    provider: str = Field(description="Embedding提供商")
    endpoint: str = Field(description="Embedding模型地址")
    api_key: str = Field(description="Embedding模型API Key")
    model: str = Field(description="Embedding模型名称")


class RerankerConfig(BaseModel):
    """Reranker配置"""

    provider: str = Field(description="Reranker提供商")
    endpoint: str = Field(description="Reranker模型地址")
    api_key: str = Field(description="Reranker模型API Key")
    model: str = Field(description="Reranker模型名称")


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


class RedisConfig(BaseModel):
    """Redis配置"""

    host: str = Field(description="Redis主机名", default="redis-db")
    port: int = Field(description="Redis端口号", default=6379)
    password: str | None = Field(description="Redis密码", default=None)
    database: int = Field(description="Redis数据库编号", default=0)
    decode_responses: bool = Field(description="是否解码响应", default=True)
    socket_timeout: float = Field(description="套接字超时时间（秒）", default=5.0)
    socket_connect_timeout: float = Field(description="连接超时时间（秒）", default=5.0)
    max_connections: int = Field(description="最大连接数", default=10)
    health_check_interval: int = Field(description="健康检查间隔（秒）", default=30)


class LLMConfig(BaseModel):
    """LLM配置"""

    provider: str = Field(description="LLM提供商")
    key: str = Field(description="LLM API密钥")
    endpoint: str = Field(description="LLM API URL地址")
    model: str = Field(description="LLM API 模型名")
    max_tokens: int | None = Field(
        description="LLM API 最大Token数", default=None)
    temperature: float | None = Field(description="LLM API 温度", default=None)


class FunctionCallConfig(BaseModel):
    """Function Call配置"""

    provider: str | None = Field(default=None, description="Function Call 提供商")
    model: str = Field(description="Function Call 模型名")
    endpoint: str = Field(description="Function Call API URL地址")
    api_key: str = Field(description="Function Call API密钥")
    max_tokens: int | None = Field(
        description="Function Call 最大Token数", default=None)
    temperature: float | None = Field(
        description="Function Call 温度", default=None)


class McpConfig(BaseModel):
    """MCP配置"""
    sse_client_init_timeout: int = Field(
        description="MCP SSE连接超时时间，单位秒", default=60)
    sse_client_read_timeout: int = Field(
        description="MCP SSE读取超时时间，单位秒", default=3600)


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


class SandboxConfig(BaseModel):
    """代码沙箱配置"""

    sandbox_service: str = Field(description="代码沙箱服务地址")


class ExtraConfig(BaseModel):
    """额外配置"""

    sql_url: str = Field(default="", description="SQL API URL")


class ConfigModel(BaseModel):
    """配置文件的校验Class"""
    no_auth: NoauthConfig = Field(description="无认证配置", default=NoauthConfig())
    admin: AdminConfig = Field(description="管理员配置", default=AdminConfig())
    deploy: DeployConfig
    login: LoginConfig
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    rag: RAGConfig
    fastapi: FastAPIConfig
    minio: MinioConfig
    mongodb: MongoDBConfig
    redis: RedisConfig
    llm: LLMConfig
    function_call: FunctionCallConfig
    mcp_config: McpConfig = Field(description="MCP配置", default=McpConfig())
    security: SecurityConfig
    check: CheckConfig
    sandbox: SandboxConfig
    extra: ExtraConfig
