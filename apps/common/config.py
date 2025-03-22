"""配置文件处理模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import os
import secrets
from typing import Optional

from dotenv import dotenv_values
from pydantic import BaseModel, Field


class ConfigModel(BaseModel):
    """配置文件的校验Class"""

    # DEPLOY
    DEPLOY_MODE: str = Field(description="oidc 部署方式", default="online")
    COOKIE_MODE: str = Field(description="COOKIE SET 方式", default="domain")
    # WEB
    WEB_FRONT_URL: str = Field(description="web前端跳转地址", default="/")
    # Redis
    REDIS_HOST: str = Field(description="Redis主机名")
    REDIS_PORT: int = Field(description="Redis端口号", default=6379)
    REDIS_PWD: str = Field(description="Redis连接密码")
    # OIDC
    DISABLE_LOGIN: bool = Field(description="是否禁用登录", default=False)
    DEFAULT_USER: Optional[str] = Field(description="禁用登录后，默认的用户ID", default=None)
    OIDC_PROVIDER: str = Field(description="OIDC Provider", default="authhub")
    OIDC_APP_ID: Optional[str] = Field(description="OIDC AppID", default=None)
    OIDC_APP_SECRET: Optional[str] = Field(description="OIDC App Secret", default=None)
    OIDC_USER_URL: Optional[str] = Field(description="OIDC USER URL", default=None)
    OIDC_STATUS_URL: Optional[str] = Field(description="OIDC 检查登录状态URL", default=None)
    OIDC_TOKEN_URL: Optional[str] = Field(description="OIDC Token获取URL", default=None)
    OIDC_LOGOUT_URL: Optional[str] = Field(description="OIDC 登出URL", default=None)
    OIDC_REFRESH_TOKEN_URL: Optional[str] = Field(description="OIDC 刷新token", default=None)
    OIDC_REDIRECT_URL: Optional[str] = Field(description="OIDC Redirect URL", default=None)
    EULER_LOGIN_API: Optional[str] = Field(description="Euler Login API", default=None)
    OIDC_ACCESS_TOKEN_EXPIRE_TIME: int = Field(description="OIDC access token过期时间", default=30)
    OIDC_REFRESH_TOKEN_EXPIRE_TIME: int = Field(description="OIDC refresh token过期时间", default=180)
    SESSION_TTL: int = Field(description="用户需要刷新Token的间隔(min)", default=30)
    # Logging
    LOG: str = Field(description="日志记录模式")
    # Embedding
    EMBEDDING_URL: str = Field(description="Embedding模型地址")
    EMBEDDING_KEY: str = Field(description="Embedding模型API Key")
    EMBEDDING_MODEL: str = Field(description="Embedding模型名称")
    # RAG
    RAG_HOST: str = Field(description="RAG服务域名")
    # FastAPI
    DOMAIN: str = Field(description="当前实例的域名")
    JWT_KEY: str = Field(description="JWT key", default=secrets.token_hex(16))
    PICKLE_KEY: str = Field(description="Pickle Key", default=secrets.token_hex(16))
    # 风控
    DETECT_TYPE: Optional[str] = Field(description="敏感词检测系统类型", default=None)
    WORDS_CHECK: Optional[str] = Field(description="AutoGPT敏感词检测系统API URL", default=None)
    WORDS_LIST: Optional[str] = Field(description="敏感词列表文件路径", default=None)
    # CSRF
    ENABLE_CSRF: bool = Field(description="是否启用CSRF Token功能", default=True)
    # MongoDB
    MONGODB_HOST: str = Field(description="MongoDB主机名")
    MONGODB_PORT: int = Field(description="MongoDB端口号", default=27017)
    MONGODB_USER: str = Field(description="MongoDB用户名")
    MONGODB_PWD: str = Field(description="MongoDB密码")
    MONGODB_DATABASE: str = Field(description="MongoDB数据库名")
    # PGSQL
    POSTGRES_HOST: str = Field(description="PGSQL主机名、端口号")
    POSTGRES_DATABASE: str = Field(description="PGSQL数据库名")
    POSTGRES_USER: str = Field(description="PGSQL用户名")
    POSTGRES_PWD: str = Field(description="PGSQL密码")
    # MinIO
    MINIO_ENDPOINT: str = Field(description="MinIO主机名、端口号")
    MINIO_ACCESS_KEY: str = Field(description="MinIO访问密钥")
    MINIO_SECRET_KEY: str = Field(description="MinIO密钥")
    MINIO_SECURE: bool = Field(description="MinIO是否启用SSL", default=False)
    # Security
    HALF_KEY1: str = Field(description="Half key 1")
    HALF_KEY2: str = Field(description="Half key 2")
    HALF_KEY3: str = Field(description="Half key 3")
    # OpenAI API
    LLM_KEY: Optional[str] = Field(description="OpenAI API 密钥", default=None)
    LLM_URL: Optional[str] = Field(description="OpenAI API URL地址", default=None)
    LLM_MODEL: Optional[str] = Field(description="OpenAI API 模型名", default=None)
    LLM_MAX_TOKENS: int = Field(description="OpenAI API 最大Token数", default=8192)
    LLM_TEMPERATURE: float = Field(description="OpenAI API 温度", default=0.7)
    # 参数提取
    SCHEDULER_BACKEND: Optional[str] = Field(description="参数猜解后端", default=None)
    SCHEDULER_MODEL: Optional[str] = Field(description="参数猜解模型名", default=None)
    SCHEDULER_URL: Optional[str] = Field(description="参数猜解 URL地址", default=None)
    SCHEDULER_API_KEY: Optional[str] = Field(description="参数猜解 API密钥", default=None)
    SCHEDULER_MAX_TOKENS: int = Field(description="参数猜解最大Token数", default=8192)
    SCHEDULER_TEMPERATURE: float = Field(description="参数猜解温度", default=0.7)
    # 插件位置
    PLUGIN_DIR: Optional[str] = Field(description="插件路径", default=None)
    # SQL接口路径
    SQL_URL: str = Field(description="Chat2DB接口路径")


class Config:
    """配置文件读取和使用Class"""

    _config: ConfigModel

    def __init__(self) -> None:
        """读取配置文件；当PROD环境变量设置时，配置文件将在读取后删除"""
        config_file = os.getenv("CONFIG")
        if config_file is None:
            config_file = "./config/.env"
        self._config = ConfigModel.model_validate(dotenv_values(config_file))

        if os.getenv("PROD"):
            os.remove(config_file)

    def __getitem__(self, key: str):  # noqa: ANN204
        """获得配置文件中特定条目的值

        :param key: 配置文件条目名
        :return: 条目的值；不存在则返回None
        """
        if hasattr(self._config, key):
            return getattr(self._config, key)

        err = f"Key {key} not found in config"
        raise KeyError(err)


config = Config()
