# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MongoDB中的数据结构"""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from apps.common.config import Config
from apps.constants import NEW_CHAT
from apps.schemas.preferences import UserPreferences
from apps.templates.generate_llm_operator_config import llm_provider_dict
from typing import Literal


class Blacklist(BaseModel):
    """
    黑名单

    Collection: blacklist
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    question: str
    answer: str
    is_audited: bool = False
    reason_type: str = ""
    reason: str | None = None
    updated_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))


class UserDomainData(BaseModel):
    """用户领域数据"""

    name: str
    count: int


class AppUsageData(BaseModel):
    """User表子项：应用使用情况数据"""

    count: int = 0
    last_used: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))


class User(BaseModel):
    """
    用户信息

    Collection: user
    外键：user - conversation
    """

    id: str = Field(alias="_id")
    user_name: str = Field(default="", description="用户名")
    last_login: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
    is_active: bool = False
    is_whitelisted: bool = False
    credit: int = 100
    api_key: str | None = None
    conversations: list[str] = []
    domains: list[UserDomainData] = []
    app_usage: dict[str, AppUsageData] = {}
    fav_apps: list[str] = []
    fav_services: list[str] = []
    is_admin: bool = Field(default=False, description="是否为管理员")
    auto_execute: bool = Field(default=True, description="是否自动执行任务")
    preferences: UserPreferences = Field(
        default_factory=UserPreferences,
        description="用户偏好设置"
    )


class LLM(BaseModel):
    """
    大模型信息

    Collection: llm
    """

    model_config = {"protected_namespaces": ()}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str = Field(default="", description="用户ID")
    title: str = Field(default=NEW_CHAT)
    icon: str = Field(
        default=llm_provider_dict["ollama"]["icon"], description="图标")
    openai_base_url: str = Field(default=Config().get_config().llm.endpoint)
    openai_api_key: str = Field(default=Config().get_config().llm.api_key)
    model_name: str = Field(default=Config().get_config().llm.model)
    max_tokens: int | None = Field(
        default=Config().get_config().llm.max_tokens)
    type: list[str] | str = Field(
        default=['chat'], description="模型类型，支持单个类型或多个类型")

    # 模型能力字段 - 基础能力
    provider: str = Field(default="", description="模型提供商")
    supports_streaming: bool = Field(default=True, description="是否支持流式输出")
    supports_function_calling: bool = Field(
        default=True, description="是否支持函数调用")
    supports_json_mode: bool = Field(default=True, description="是否支持JSON模式")
    supports_structured_output: bool = Field(
        default=False, description="是否支持结构化输出")
    
    # 推理能力
    supports_thinking: bool = Field(default=False, description="是否支持思维链")
    can_toggle_thinking: bool = Field(
        default=False, description="是否支持开关思维链（仅当supports_thinking=True时有效）")
    supports_reasoning_content: bool = Field(
        default=False, description="是否返回reasoning_content字段")
    
    # 参数支持
    max_tokens_param: str = Field(
        default="max_tokens", description="最大token参数名")
    supports_temperature: bool = Field(default=True, description="是否支持temperature参数")
    supports_top_p: bool = Field(default=True, description="是否支持top_p参数")
    supports_top_k: bool = Field(default=False, description="是否支持top_k参数")
    supports_frequency_penalty: bool = Field(default=False, description="是否支持frequency_penalty参数")
    supports_presence_penalty: bool = Field(default=False, description="是否支持presence_penalty参数")
    supports_min_p: bool = Field(default=False, description="是否支持min_p参数")
    
    # 高级功能
    supports_response_format: bool = Field(default=True, description="是否支持response_format参数")
    supports_tools: bool = Field(default=True, description="是否支持tools参数")
    supports_tool_choice: bool = Field(default=True, description="是否支持tool_choice参数")
    supports_extra_body: bool = Field(default=True, description="是否支持extra_body参数")
    supports_stream_options: bool = Field(default=True, description="是否支持stream_options参数")
    
    # 特殊参数
    supports_enable_thinking: bool = Field(default=False, description="是否支持enable_thinking参数")
    supports_thinking_budget: bool = Field(default=False, description="是否支持思维链token预算")
    supports_enable_search: bool = Field(default=False, description="是否支持联网搜索")
    
    # 其他信息
    notes: str = Field(default="", description="备注信息")

    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))

    def normalize_type(self) -> list[str]:
        """标准化type字段为列表格式"""
        if isinstance(self.type, str):
            return [self.type]
        return self.type

    def model_dump(self, **kwargs):
        """重写model_dump方法，确保type字段存储为列表"""
        data = super().model_dump(**kwargs)
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = [data['type']]
        return data


class LLMItem(BaseModel):
    """大模型信息"""

    model_config = {"protected_namespaces": ()}

    llm_id: str = Field(default="")
    model_name: str = Field(default=Config().get_config().llm.model)
    icon: str = Field(default=llm_provider_dict["ollama"]["icon"])


class KnowledgeBaseItem(BaseModel):
    """知识库信息"""

    kb_id: str
    kb_name: str


class Conversation(BaseModel):
    """
    对话信息

    Collection: conversation
    外键：conversation - task, document, record_group
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    title: str = NEW_CHAT
    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
    app_id: str | None = Field(default="")
    tasks: list[str] = []
    unused_docs: list[str] = []
    record_groups: list[str] = []
    debug: bool = Field(default=False)
    llm: LLMItem | None = None
    kb_list: list[KnowledgeBaseItem] = Field(default=[])


class Document(BaseModel):
    """
    文件信息

    Collection: document
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    name: str
    type: str
    size: float
    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
    conversation_id: str | None = Field(default=None)


class Audit(BaseModel):
    """
    审计日志

    Collection: audit
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str | None = None
    http_method: str
    created_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
    module: str
    client_ip: str | None = None
    message: str


class Domain(BaseModel):
    """
    领域信息

    Collection: domain
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    definition: str
    updated_at: float = Field(default_factory=lambda: round(
        datetime.now(tz=UTC).timestamp(), 3))
