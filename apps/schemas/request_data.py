# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 请求体"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.common.config import Config
from apps.schemas.appcenter import AppData
from apps.schemas.enum_var import CommentType, LanguageType
from apps.schemas.flow_topology import FlowItem
from apps.schemas.mcp import MCPType
from apps.schemas.message import FlowParams
from apps.schemas.preferences import ReasoningModelPreference, EmbeddingModelPreference, RerankerModelPreference


class RequestDataApp(BaseModel):
    """模型对话中包含的app信息"""

    app_id: str = Field(description="应用ID", alias="appId")
    flow_id: str | None = Field(default=None, description="Flow ID", alias="flowId")


class MockRequestData(BaseModel):
    """POST /api/mock/chat的请求体"""

    app_id: str = Field(default="", description="应用ID", alias="appId")
    flow_id: str = Field(default="", description="流程ID", alias="flowId")
    conversation_id: str = Field(..., description="会话ID", alias="conversationId")
    question: str = Field(..., description="问题", alias="question")


class RequestDataFeatures(BaseModel):
    """POST /api/chat的features字段数据"""

    max_tokens: int | None = Field(default=Config().get_config().llm.max_tokens, description="最大生成token数")
    context_num: int = Field(default=5, description="上下文消息数量", le=10, ge=0)


class RequestData(BaseModel):
    """POST /api/chat 请求的总的数据结构"""

    question: str | None = Field(default=None, max_length=2000, description="用户输入")
    conversation_id: str | None = Field(default=None, alias="conversationId", description="聊天ID")
    group_id: str | None = Field(default=None, alias="groupId", description="问答组ID")
    language: LanguageType = Field(default=LanguageType.CHINESE, description="语言")
    files: list[str] = Field(default=[], description="文件列表")
    app: RequestDataApp | None = Field(default=None, description="应用")
    debug: bool = Field(default=False, description="是否调试")
    task_id: str | None = Field(default=None, alias="taskId", description="任务ID")
    params: FlowParams | bool | None = Field(default=None, description="流执行过程中的参数补充", alias="params")
    llm_id: str | None = Field(default=None, alias="llmId", description="选中的大模型ID")
    enable_thinking: bool = Field(default=False, alias="enableThinking", description="是否启用思维链")
    auto_execute: bool | None = Field(default=None, alias="autoExecute", description="是否自动执行（会话级设置，优先于用户全局设置）")


class QuestionBlacklistRequest(BaseModel):
    """POST /api/blacklist/question 请求数据结构"""

    id: str
    question: str
    answer: str
    is_deletion: int


class UserBlacklistRequest(BaseModel):
    """POST /api/blacklist/user 请求数据结构"""

    user_sub: str
    is_ban: int


class AbuseRequest(BaseModel):
    """POST /api/blacklist/complaint 请求数据结构"""

    record_id: str
    reason: str
    reason_type: str


class AbuseProcessRequest(BaseModel):
    """POST /api/blacklist/abuse 请求数据结构"""

    id: str
    is_deletion: int


class CreateAppRequest(AppData):
    """POST /api/app 请求数据结构"""

    app_id: str | None = Field(None, alias="appId", description="应用ID")


class ModFavAppRequest(BaseModel):
    """PUT /api/app/{appId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class UpdateMCPServiceRequest(BaseModel):
    """POST /api/mcpservice 请求数据结构"""

    service_id: str | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(..., description="MCP服务描述")
    overview: str = Field(..., description="MCP服务概述")
    config: dict[str, Any] = Field(..., description="MCP服务配置")
    mcp_type: MCPType = Field(description="MCP传输协议(Stdio/SSE/Streamable)", default=MCPType.STDIO, alias="mcpType")


class ActiveMCPServiceRequest(BaseModel):
    """POST /api/mcp/{serviceId} 请求数据结构"""

    active: bool = Field(description="是否激活mcp服务")
    mcp_env: dict[str, Any] | None = Field(default=None, description="MCP服务环境变量", alias="mcpEnv")


class UpdateServiceRequest(BaseModel):
    """POST /api/service 请求数据结构"""

    service_id: str | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    data: dict[str, Any] = Field(..., description="对应 YAML 内容的数据对象")


class ModFavServiceRequest(BaseModel):
    """PUT /api/service/{serviceId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class ClientSessionData(BaseModel):
    """客户端Session信息"""

    session_id: str | None = Field(default=None)


class ModifyConversationData(BaseModel):
    """修改会话信息"""

    title: str = Field(..., min_length=1, max_length=2000)


class DeleteConversationData(BaseModel):
    """删除会话"""

    conversation_list: list[str] = Field(alias="conversationList")


class AddCommentData(BaseModel):
    """添加评论"""

    record_id: str
    group_id: str
    comment: CommentType
    dislike_reason: str = Field(default="", max_length=200)
    reason_link: str = Field(default="", max_length=200)
    reason_description: str = Field(default="", max_length=500)


class PostDomainData(BaseModel):
    """添加领域"""

    domain_name: str = Field(..., min_length=1, max_length=100)
    domain_description: str = Field(..., max_length=2000)


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem


class UpdateLLMReq(BaseModel):
    """更新大模型请求体"""

    model_config = {"protected_namespaces": ()}

    icon: str = Field(description="图标", default="")
    openai_base_url: str = Field(default="", description="OpenAI API Base URL", alias="openaiBaseUrl")
    openai_api_key: str = Field(default="", description="OpenAI API Key", alias="openaiApiKey")
    model_name: str = Field(default="", description="模型名称", alias="modelName")
    max_tokens: int = Field(default=8192, description="最大token数", alias="maxTokens")
    type: Literal['chat', 'image', 'video', 'speech', 'embedding', 'reranker'] = Field(default='chat', description="模型类型")
    
    # 可选的能力字段，如果不提供则自动从model_registry推断
    provider: str | None = Field(default=None, description="模型提供商")
    supports_thinking: bool | None = Field(default=None, description="是否支持思维链")
    can_toggle_thinking: bool | None = Field(default=None, description="是否支持开关思维链")
    supports_function_calling: bool | None = Field(default=None, description="是否支持函数调用")
    supports_json_mode: bool | None = Field(default=None, description="是否支持JSON模式")
    supports_structured_output: bool | None = Field(default=None, description="是否支持结构化输出")
    max_tokens_param: str | None = Field(default=None, description="最大token参数名")
    notes: str | None = Field(default=None, description="备注信息")


class DeleteLLMReq(BaseModel):
    """删除大模型请求体"""

    llm_id: str = Field(description="大模型ID", alias="llmId")


class UpdateKbReq(BaseModel):
    """更新知识库请求体"""

    kb_ids: list[str] = Field(description="知识库ID列表", alias="kbIds", default=[])


class UserUpdateRequest(BaseModel):
    """更新用户信息请求体"""

    auto_execute: bool = Field(default=False, description="是否自动执行", alias="autoExecute")


class UserPreferencesRequest(BaseModel):
    """更新用户偏好设置请求体"""

    reasoning_model_preference: ReasoningModelPreference | None = Field(
        default=None, 
        description="推理模型偏好", 
        alias="reasoningModelPreference"
    )
    embedding_model_preference: EmbeddingModelPreference | None = Field(
        default=None, 
        description="嵌入模型偏好", 
        alias="embeddingModelPreference"
    )
    reranker_preference: RerankerModelPreference | None = Field(
        default=None, 
        description="重排序模型偏好", 
        alias="rerankerPreference"
    )
    chain_of_thought_preference: bool | None = Field(
        default=None,
        description="思维链偏好",
        alias="chainOfThoughtPreference"
    )
    auto_execute_preference: bool | None = Field(
        default=None,
        description="自动执行偏好",
        alias="autoExecutePreference"
    )