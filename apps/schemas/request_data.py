# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 请求体"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models import LanguageType, LLMProvider, LLMType

from .flow_topology import FlowItem


class RequestDataApp(BaseModel):
    """模型对话中包含的app信息"""

    app_id: uuid.UUID = Field(description="应用ID", alias="appId")
    flow_id: str | None = Field(default=None, description="Flow ID", alias="flowId")
    params: dict[str, Any] | None = Field(
        default=None, description="流执行过程中的参数补充", alias="params",
    )


class RequestData(BaseModel):
    """POST /api/chat 请求的总的数据结构"""

    question: str = Field(max_length=2000, description="用户输入")
    conversation_id: uuid.UUID | None = Field(
        default=None, alias="conversationId", description="聊天ID",
    )
    language: LanguageType = Field(default=LanguageType.CHINESE, description="语言")
    app: RequestDataApp | None = Field(default=None, description="应用")
    llm_id: str = Field(alias="llmId", description="大模型ID")
    kb_ids: list[uuid.UUID] = Field(default=[], description="知识库ID列表")


class PostTagData(BaseModel):
    """添加领域"""

    tag: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=2000)


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem


class UpdateLLMReq(BaseModel):
    """更新大模型请求体"""

    llm_id: str | None = Field(default=None, description="大模型ID", alias="id")
    base_url: str = Field(default="", description="OpenAI API Base URL", alias="baseUrl")
    api_key: str = Field(default="", description="OpenAI API Key", alias="apiKey")
    model_name: str | None = Field(default=None, description="模型名称", alias="modelName")
    max_tokens: int = Field(default=8192, description="最大token数", alias="maxTokens")
    provider: LLMProvider = Field(description="大模型提供商", alias="provider")
    ctx_length: int = Field(description="上下文长度", alias="ctxLength")
    llm_description: str = Field(default="", description="大模型描述", alias="llmDescription")
    llm_type: list[LLMType] | None = Field(default=None, description="大模型类型列表", alias="llmType")
    extra_data: dict[str, Any] | None = Field(default=None, description="额外数据", alias="extraData")


class UpdateSpecialLlmReq(BaseModel):
    """更新用户特殊LLM请求体"""

    functionLLM: str = Field(description="Function Call LLM ID")  # noqa: N815
    embeddingLLM: str = Field(description="Embedding LLM ID")  # noqa: N815


class UpdateUserKnowledgebaseReq(BaseModel):
    """更新知识库请求体"""

    kb_ids: list[uuid.UUID] = Field(description="知识库ID列表", alias="kbIds", default=[])


class UserUpdateRequest(BaseModel):
    """更新用户信息请求体"""

    auto_execute: bool = Field(default=False, description="是否自动执行", alias="autoExecute")
