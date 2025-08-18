# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构"""

from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.appcenter import AppCenterCardItem, AppData
from apps.schemas.collection import Blacklist, Document
from apps.schemas.enum_var import DocumentStatus
from apps.schemas.flow_topology import (
    FlowItem,
    NodeMetaDataItem,
    NodeServiceItem,
    PositionItem,
)
from apps.schemas.parameters import (
    Type,
    NumberOperate,
    StringOperate,
    ListOperate,
    BoolOperate,
    DictOperate,
)
from apps.schemas.mcp import MCPInstallStatus, MCPTool, MCPType
from apps.schemas.record import RecordData
from apps.schemas.user import UserInfo
from apps.templates.generate_llm_operator_config import llm_provider_dict
from apps.common.config import Config


class ResponseData(BaseModel):
    """基础返回数据结构"""

    code: int
    message: str
    result: Any


class PostClientSessionMsg(BaseModel):
    """POST /api/client/session Result数据结构"""

    session_id: str
    user_sub: str | None = None


class PostClientSessionRsp(ResponseData):
    """POST /api/client/session 返回数据结构"""

    result: PostClientSessionMsg


class AuthUserMsg(BaseModel):
    """GET /api/auth/user Result数据结构"""

    user_sub: str
    revision: bool
    is_admin: bool
    auto_execute: bool


class AuthUserRsp(ResponseData):
    """GET /api/auth/user 返回数据结构"""

    result: AuthUserMsg


class HealthCheckRsp(BaseModel):
    """GET /health_check 返回数据结构"""

    status: str


class GetBlacklistUserMsg(BaseModel):
    """GET /api/blacklist/user Result数据结构"""

    user_subs: list[str]


class GetBlacklistUserRsp(ResponseData):
    """GET /api/blacklist/user 返回数据结构"""

    result: GetBlacklistUserMsg


class GetBlacklistQuestionMsg(BaseModel):
    """GET /api/blacklist/question Result数据结构"""

    question_list: list[Blacklist]


class GetBlacklistQuestionRsp(ResponseData):
    """GET /api/blacklist/question 返回数据结构"""

    result: GetBlacklistQuestionMsg


class LLMIteam(BaseModel):
    """GET /api/conversation Result数据结构"""

    icon: str = Field(default=llm_provider_dict["ollama"]["icon"])
    llm_id: str = Field(alias="llmId", default="empty")
    model_name: str = Field(alias="modelName", default=Config().get_config().llm.model)


class KbIteam(BaseModel):
    """GET /api/conversation Result数据结构"""

    kb_id: str = Field(alias="kbId")
    kb_name: str = Field(alias="kbName")


class ConversationListItem(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversation_id: str = Field(alias="conversationId")
    title: str
    doc_count: int = Field(alias="docCount")
    created_time: str = Field(alias="createdTime")
    app_id: str = Field(alias="appId")
    debug: bool = Field(alias="debug")
    llm: LLMIteam | None = Field(alias="llm", default=None)
    kb_list: list[KbIteam] = Field(alias="kbList", default=[])


class ConversationListMsg(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversations: list[ConversationListItem]


class ConversationListRsp(ResponseData):
    """GET /api/conversation 返回数据结构"""

    result: ConversationListMsg


class DeleteConversationMsg(BaseModel):
    """DELETE /api/conversation Result数据结构"""

    conversation_id_list: list[str] = Field(alias="conversationIdList")


class DeleteConversationRsp(ResponseData):
    """DELETE /api/conversation 返回数据结构"""

    result: DeleteConversationMsg


class AddConversationMsg(BaseModel):
    """POST /api/conversation Result数据结构"""

    conversation_id: str = Field(alias="conversationId")


class AddConversationRsp(ResponseData):
    """POST /api/conversation 返回数据结构"""

    result: AddConversationMsg


class UpdateConversationRsp(ResponseData):
    """POST /api/conversation 返回数据结构"""

    result: ConversationListItem


class RecordListMsg(BaseModel):
    """GET /api/record/{conversation_id} Result数据结构"""

    records: list[RecordData]


class RecordListRsp(ResponseData):
    """GET /api/record/{conversation_id} 返回数据结构"""

    result: RecordListMsg


class ConversationDocumentItem(Document):
    """GET /api/document/{conversation_id} Result内元素数据结构"""

    id: str = Field(alias="_id", default="")
    user_sub: None = None
    status: DocumentStatus
    conversation_id: None = None

    class Config:
        """配置"""

        populate_by_name = True


class ConversationDocumentMsg(BaseModel):
    """GET /api/document/{conversation_id} Result数据结构"""

    documents: list[ConversationDocumentItem] = []


class ConversationDocumentRsp(ResponseData):
    """GET /api/document/{conversation_id} 返回数据结构"""

    result: ConversationDocumentMsg


class UploadDocumentMsgItem(Document):
    """POST /api/document/{conversation_id} 返回数据结构"""

    id: str = Field(alias="_id", default="")
    user_sub: None = None
    created_at: None = None
    conversation_id: None = None

    class Config:
        """配置"""

        populate_by_name = True


class UploadDocumentMsg(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    documents: list[UploadDocumentMsgItem]


class UploadDocumentRsp(ResponseData):
    """POST /api/document/{conversation_id} 返回数据结构"""

    result: UploadDocumentMsg


class OidcRedirectMsg(BaseModel):
    """GET /api/auth/redirect Result数据结构"""

    url: str


class OidcRedirectRsp(ResponseData):
    """GET /api/auth/redirect 返回数据结构"""

    result: OidcRedirectMsg


class KnowledgeBaseItem(BaseModel):
    """知识库列表项数据结构"""

    kb_id: str = Field(..., alias="kbId", description="知识库ID")
    kb_name: str = Field(..., description="知识库名称", alias="kbName")
    description: str = Field(..., description="知识库描述")
    is_used: bool = Field(..., description="是否使用", alias="isUsed")


class TeamKnowledgeBaseItem(BaseModel):
    """团队知识库列表项数据结构"""

    team_id: str = Field(..., alias="teamId", description="团队ID")
    team_name: str = Field(..., alias="teamName", description="团队名称")
    kb_list: list[KnowledgeBaseItem] = Field(default=[], description="知识库列表")


class ListTeamKnowledgeMsg(BaseModel):
    """GET /api/knowledge Result数据结构"""

    team_kb_list: list[TeamKnowledgeBaseItem] = Field(default=[], alias="teamKbList", description="团队知识库列表")


class ListTeamKnowledgeRsp(ResponseData):
    """GET /api/knowledge 返回数据结构"""

    result: ListTeamKnowledgeMsg


class BaseAppOperationMsg(BaseModel):
    """基础应用操作Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")


class BaseAppOperationRsp(ResponseData):
    """基础应用操作返回数据结构"""

    result: BaseAppOperationMsg


class AppMcpServiceInfo(BaseModel):
    """应用关联的MCP服务信息"""

    id: str = Field(..., description="MCP服务ID")
    name: str = Field(default="", description="MCP服务名称")
    description: str = Field(default="", description="MCP服务简介")


class GetAppPropertyMsg(AppData):
    """GET /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    published: bool = Field(..., description="是否已发布")
    mcp_service: list[AppMcpServiceInfo] = Field(default=[], alias="mcpService", description="MCP服务信息列表")
    llm: LLMIteam | None = Field(alias="llm", default=None)


class GetAppPropertyRsp(ResponseData):
    """GET /api/app/{appId} 返回数据结构"""

    result: GetAppPropertyMsg


class ModFavAppMsg(BaseModel):
    """PUT /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    favorited: bool = Field(..., description="是否已收藏")


class ModFavAppRsp(ResponseData):
    """PUT /api/app/{appId} 返回数据结构"""

    result: ModFavAppMsg


class GetAppListMsg(BaseModel):
    """GET /api/app Result数据结构"""

    page_number: int = Field(..., alias="currentPage", description="当前页码")
    app_count: int = Field(..., alias="totalApps", description="总应用数")
    applications: list[AppCenterCardItem] = Field(..., description="应用列表")


class GetAppListRsp(ResponseData):
    """GET /api/app 返回数据结构"""

    result: GetAppListMsg


class RecentAppListItem(BaseModel):
    """GET /api/app/recent 列表项数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    name: str = Field(..., description="应用名称")


class RecentAppList(BaseModel):
    """GET /api/app/recent Result数据结构"""

    applications: list[RecentAppListItem] = Field(..., description="最近使用的应用列表")


class GetRecentAppListRsp(ResponseData):
    """GET /api/app/recent 返回数据结构"""

    result: RecentAppList


class ServiceCardItem(BaseModel):
    """语义接口中心：服务卡片数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    description: str = Field(..., description="服务简介")
    icon: str = Field(..., description="服务图标")
    author: str = Field(..., description="服务作者")
    favorited: bool = Field(..., description="是否已收藏")


class ServiceApiData(BaseModel):
    """语义接口中心：服务 API 接口属性数据结构"""

    name: str = Field(..., description="接口名称")
    path: str = Field(..., description="接口路径")
    description: str = Field(..., description="接口描述")


class BaseServiceOperationMsg(BaseModel):
    """语义接口中心：基础服务操作Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")


class GetServiceListMsg(BaseModel):
    """GET /api/service Result数据结构"""

    current_page: int = Field(..., alias="currentPage", description="当前页码")
    total_count: int = Field(..., alias="totalCount", description="总服务数")
    services: list[ServiceCardItem] = Field(..., description="解析后的服务列表")


class GetServiceListRsp(ResponseData):
    """GET /api/service 返回数据结构"""

    result: GetServiceListMsg = Field(..., title="Result")


class UpdateServiceMsg(BaseModel):
    """语义接口中心：服务属性数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    apis: list[ServiceApiData] = Field(..., description="解析后的接口列表")


class UpdateServiceRsp(ResponseData):
    """POST /api/service 返回数据结构"""

    result: UpdateServiceMsg = Field(..., title="Result")


class GetServiceDetailMsg(BaseModel):
    """GET /api/service/{serviceId} Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    apis: list[ServiceApiData] | None = Field(default=None, description="解析后的接口列表")
    data: dict[str, Any] | None = Field(default=None, description="YAML 内容数据对象")


class GetServiceDetailRsp(ResponseData):
    """GET /api/service/{serviceId} 返回数据结构"""

    result: GetServiceDetailMsg = Field(..., title="Result")


class DeleteServiceRsp(ResponseData):
    """DELETE /api/service/{serviceId} 返回数据结构"""

    result: BaseServiceOperationMsg = Field(..., title="Result")


class ModFavServiceMsg(BaseModel):
    """PUT /api/service/{serviceId} Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")
    favorited: bool = Field(..., description="是否已收藏")


class ModFavServiceRsp(ResponseData):
    """PUT /api/service/{serviceId} 返回数据结构"""

    result: ModFavServiceMsg = Field(..., title="Result")


class NodeServiceListMsg(BaseModel):
    """GET /api/flow/service result"""

    services: list[NodeServiceItem] = Field(description="服务列表", default=[])


class NodeServiceListRsp(ResponseData):
    """GET /api/flow/service 返回数据结构"""

    result: NodeServiceListMsg


class MCPServiceCardItem(BaseModel):
    """插件中心：MCP服务卡片数据结构"""

    mcpservice_id: str = Field(..., alias="mcpserviceId", description="mcp服务ID")
    name: str = Field(..., description="mcp服务名称")
    description: str = Field(..., description="mcp服务简介")
    icon: str = Field(..., description="mcp服务图标")
    author: str = Field(..., description="mcp服务作者")
    is_active: bool = Field(default=False, alias="isActive", description="mcp服务是否激活")
    status: MCPInstallStatus = Field(default=MCPInstallStatus.INSTALLING, description="mcp服务状态")


class BaseMCPServiceOperationMsg(BaseModel):
    """插件中心：MCP服务操作Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")


class GetMCPServiceListMsg(BaseModel):
    """GET /api/service Result数据结构"""

    current_page: int = Field(..., alias="currentPage", description="当前页码")
    services: list[MCPServiceCardItem] = Field(..., description="解析后的服务列表")


class GetMCPServiceListRsp(ResponseData):
    """GET /api/service 返回数据结构"""

    result: GetMCPServiceListMsg = Field(..., title="Result")


class UpdateMCPServiceMsg(BaseModel):
    """插件中心：MCP服务属性数据结构"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    name: str = Field(..., description="MCP服务名称")


class UpdateMCPServiceRsp(ResponseData):
    """POST /api/mcp_service 返回数据结构"""

    result: UpdateMCPServiceMsg = Field(..., title="Result")


class UploadMCPServiceIconMsg(BaseModel):
    """POST /api/mcp_service/icon Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    url: str = Field(..., description="图标URL")


class UploadMCPServiceIconRsp(ResponseData):
    """POST /api/mcp_service/icon 返回数据结构"""

    result: UploadMCPServiceIconMsg = Field(..., title="Result")


class GetMCPServiceDetailMsg(BaseModel):
    """GET /api/mcp_service/{serviceId} Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    icon: str = Field(description="图标", default="")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(description="MCP服务描述")
    overview: str = Field(description="MCP服务概述")
    status: MCPInstallStatus = Field(
        description="MCP服务状态",
        default=MCPInstallStatus.INIT,
    )
    tools: list[MCPTool] = Field(description="MCP服务Tools列表", default=[])


class EditMCPServiceMsg(BaseModel):
    """编辑MCP服务"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    icon: str = Field(description="图标", default="")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(description="MCP服务描述")
    overview: str = Field(description="MCP服务概述")
    data: str = Field(description="MCP服务配置")
    mcp_type: MCPType = Field(alias="mcpType", description="MCP 类型")


class GetMCPServiceDetailRsp(ResponseData):
    """GET /api/service/{serviceId} 返回数据结构"""

    result: GetMCPServiceDetailMsg | EditMCPServiceMsg = Field(..., title="Result")


class DeleteMCPServiceRsp(ResponseData):
    """DELETE /api/service/{serviceId} 返回数据结构"""

    result: BaseMCPServiceOperationMsg = Field(..., title="Result")


class NodeMetaDataRsp(ResponseData):
    """GET /api/flow/service/node 返回数据结构"""

    result: NodeMetaDataItem


class FlowStructureGetMsg(BaseModel):
    """GET /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructureGetRsp(ResponseData):
    """GET /api/flow 返回数据结构"""

    result: FlowStructureGetMsg


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem
    focus_point: PositionItem = Field(alias="focusPoint", default=PositionItem())


class FlowStructurePutMsg(BaseModel):
    """PUT /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructurePutRsp(ResponseData):
    """PUT /api/flow 返回数据结构"""

    result: FlowStructurePutMsg


class FlowStructureDeleteMsg(BaseModel):
    """DELETE /api/flow/ result"""

    flow_id: str = Field(alias="flowId", default="")


class FlowStructureDeleteRsp(ResponseData):
    """DELETE /api/flow/ 返回数据结构"""

    result: FlowStructureDeleteMsg


class UserGetMsp(BaseModel):
    """GET /api/user result"""
    total: int = Field(default=0)
    user_info_list: list[UserInfo] = Field(alias="userInfoList", default=[])


class UserGetRsp(ResponseData):
    """GET /api/user 返回数据结构"""

    result: UserGetMsp


class ActiveMCPServiceRsp(ResponseData):
    """POST /api/mcp/active/{serviceId} 返回数据结构"""

    result: BaseMCPServiceOperationMsg = Field(..., title="Result")


class LLMProvider(BaseModel):
    """LLM提供商数据结构"""

    provider: str = Field(description="LLM提供商")
    description: str = Field(description="LLM提供商描述")
    url: str | None = Field(default=None, description="LLM提供商URL")
    icon: str = Field(description="LLM提供商图标")


class ListLLMProviderRsp(ResponseData):
    """GET /api/llm/provider 返回数据结构"""

    result: list[LLMProvider] = Field(default=[], title="Result")


class LLMProviderInfo(BaseModel):
    """LLM数据结构"""

    llm_id: str = Field(alias="llmId", description="LLM ID")
    icon: str = Field(default="", description="LLM图标", max_length=25536)
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API Base URL",
        alias="openaiBaseUrl",
    )
    openai_api_key: str = Field(
        description="OpenAI API Key",
        alias="openaiApiKey",
        default="",
    )
    model_name: str = Field(description="模型名称", alias="modelName")
    max_tokens: int | None = Field(default=None, description="最大token数", alias="maxTokens")
    is_editable: bool = Field(default=True, description="是否可编辑", alias="isEditable")


class ListLLMRsp(ResponseData):
    """GET /api/llm 返回数据结构"""

    result: list[LLMProviderInfo] = Field(default=[], title="Result")


class ParamsNode(BaseModel):
    """参数数据结构"""
    param_name: str = Field(..., description="参数名称", alias="paramName")
    param_path: str = Field(..., description="参数路径", alias="paramPath")
    param_type: Type = Field(..., description="参数类型", alias="paramType")
    sub_params: list["ParamsNode"] | None = Field(
        default=None, description="子参数列表", alias="subParams"
    )


class StepParams(BaseModel):
    """参数数据结构"""
    step_id: str = Field(..., description="步骤ID", alias="stepId")
    name: str = Field(..., description="Step名称")
    params_node: ParamsNode | None = Field(
        default=None, description="参数节点", alias="paramsNode")


class GetParamsRsp(ResponseData):
    """GET /api/params 返回数据结构"""

    result: list[StepParams] = Field(
        default=[], description="参数列表", alias="result"
    )


class OperateAndBindType(BaseModel):
    """操作和绑定类型数据结构"""

    operate: NumberOperate | StringOperate | ListOperate | BoolOperate | DictOperate = Field(description="操作类型")
    bind_type: Type = Field(description="绑定类型")


class GetOperaRsp(ResponseData):
    """GET /api/operate 返回数据结构"""

    result: list[OperateAndBindType] = Field(..., title="Result")
