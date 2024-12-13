# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
import os
from typing import Optional
import secrets

from dotenv import dotenv_values
from pydantic import BaseModel, Field


class ConfigModel(BaseModel):
    """
    配置文件的校验Class
    """

    # DEPLOY
    DEPLOY_MODE: str = Field(description="oidc 部署方式", default="online")
    COOKIE_MODE: str = Field(description="COOKIE SET 方式", default="domain")
    # WEB
    WEB_FRONT_URL: str = Field(description="web前端地址")
    # Redis
    REDIS_HOST: str = Field(description="Redis主机名")
    REDIS_PORT: int = Field(description="Redis端口号", default=6379)
    REDIS_PWD: str = Field(description="Redis连接密码")
    # OIDC
    DISABLE_LOGIN: bool = Field(description="是否禁用登录", default=False)
    DEFAULT_USER: Optional[str] = Field(description="禁用登录后，默认的用户ID", default=None)
    OIDC_APP_ID: Optional[str] = Field(description="OIDC AppID", default=None)
    OIDC_APP_SECRET: Optional[str] = Field(description="OIDC App Secret", default=None)
    OIDC_USER_URL: Optional[str] = Field(description="OIDC USER URL", default=None)
    OIDC_TOKEN_URL: Optional[str] = Field(description="OIDC Token获取URL", default=None)
    OIDC_REFRESH_TOKEN_URL: Optional[str] = Field(description="OIDC 刷新token", default=None)
    OIDC_REDIRECT_URL: Optional[str] = Field(description="OIDC Redirect URL", default=None)
    EULER_LOGIN_API: Optional[str] = Field(description="Euler Login API", default=None)
    OIDC_ACCESS_TOKEN_EXPIRE_TIME: int = Field(description="OIDC access token过期时间", default=30)
    OIDC_REFRESH_TOKEN_EXPIRE_TIME: int = Field(description="OIDC refresh token过期时间", default=180)
    SESSION_TTL: int = Field(description="用户需要刷新Token的间隔(min)", default=30)
    # Logging
    LOG: str = Field(description="日志记录模式")
    # Vectorize
    VECTORIZE_HOST: str = Field(description="Vectorize服务域名")
    # RAG
    RAG_HOST: str = Field(description="RAG服务域名")
    RAG_KB_SN: Optional[str] = Field(description="RAG 资产库", default=None)
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
    # MySQL
    MYSQL_HOST: str = Field(description="MySQL主机名、端口号")
    MYSQL_DATABASE: str = Field(description="MySQL数据库名")
    MYSQL_USER: str = Field(description="MySQL用户名")
    MYSQL_PWD: str = Field(description="MySQL密码")
    # PGSQL
    POSTGRES_HOST: str = Field(description="PGSQL主机名、端口号")
    POSTGRES_DATABASE: str = Field(description="PGSQL数据库名")
    POSTGRES_USER: str = Field(description="PGSQL用户名")
    POSTGRES_PWD: str = Field(description="PGSQL密码")
    # Security
    HALF_KEY1: str = Field(description="Half key 1")
    HALF_KEY2: str = Field(description="Half key 2")
    HALF_KEY3: str = Field(description="Half key 3")
    # 模型类型
    MODEL: str = Field(description="选择的模型类型", default="openai")
    # OpenAI API
    LLM_KEY: Optional[str] = Field(description="OpenAI API 密钥", default=None)
    LLM_URL: Optional[str] = Field(description="OpenAI API URL地址", default=None)
    LLM_MODEL: Optional[str] = Field(description="OpenAI API 模型名", default=None)
    # 星火大模型
    SPARK_APP_ID: Optional[str] = Field(description="星火大模型API 应用名", default=None)
    SPARK_API_KEY: Optional[str] = Field(description="星火大模型API 密钥名", default=None)
    SPARK_API_SECRET: Optional[str] = Field(description="星火大模型API 密钥值", default=None)
    SPARK_API_URL: Optional[str] = Field(description="星火大模型API URL地址", default=None)
    SPARK_LLM_DOMAIN: Optional[str] = Field(description="星火大模型API 领域名", default=None)
    # 参数猜解
    SCHEDULER_BACKEND: Optional[str] = Field(description="参数猜解后端", default=None)
    SCHEDULER_URL: Optional[str] = Field(description="参数猜解 URL地址", default=None)
    SCHEDULER_API_KEY: Optional[str] = Field(description="参数猜解 API密钥", default=None)
    SCHEDULER_STRUCTURED_OUTPUT: Optional[bool] = Field(description="是否启用结构化输出", default=True)
    # 插件位置
    PLUGIN_DIR: Optional[str] = Field(description="插件路径", default=None)
    # 临时路径
    TEMP_DIR: str = Field(description="临时目录位置", default="/tmp")
    # SQL接口路径
    SQL_URL: str = Field(description="Chat2DB接口路径")


class Config:
    """
    配置文件读取和使用Class
    """

    config: ConfigModel

    def __init__(self):
        """
        读取配置文件；当PROD环境变量设置时，配置文件将在读取后删除
        """
        if os.getenv("CONFIG"):
            config_file = os.getenv("CONFIG")
        else:
            config_file = "./config/.env"
        self.config = ConfigModel(**(dotenv_values(config_file)))

        if os.getenv("PROD"):
            os.remove(config_file)

    def __getitem__(self, key):
        """
        获得配置文件中特定条目的值
        :param key: 配置文件条目名
        :return: 条目的值；不存在则返回None
        """
        if key in self.config.__dict__:
            return self.config.__dict__[key]
        else:
            return None


config = Config()
