"""FastAPI 返回数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.appcenter import AppCenterCardItem, AppData
from apps.entities.collection import Blacklist, Document
from apps.entities.enum_var import DocumentStatus
from apps.entities.flow_topology import (
    FlowItem,
    NodeMetaDataItem,
    NodeServiceItem,
    PositionItem,
)
from apps.entities.record import RecordData


class ResponseData(BaseModel):
    """基础返回数据结构"""

    code: int
    message: str
    result: dict[str, Any]


class _GetAuthKeyMsg(BaseModel):
    """GET /api/auth/key Result数据结构"""

    api_key_exists: bool


class GetAuthKeyRsp(ResponseData):
    """GET /api/auth/key 返回数据结构"""

    result: _GetAuthKeyMsg


class PostAuthKeyMsg(BaseModel):
    """POST /api/auth/key Result数据结构"""

    api_key: str


class PostAuthKeyRsp(ResponseData):
    """POST /api/auth/key 返回数据结构"""

    result: PostAuthKeyMsg


class PostClientSessionMsg(BaseModel):
    """POST /api/client/session Result数据结构"""

    session_id: str
    user_sub: Optional[str] = None


class PostClientSessionRsp(ResponseData):
    """POST /api/client/session 返回数据结构"""

    result: PostClientSessionMsg


class AuthUserMsg(BaseModel):
    """GET /api/auth/user Result数据结构"""

    user_sub: str
    revision: bool


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


class ConversationListItem(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversation_id: str = Field(alias="conversationId")
    title: str
    doc_count: int = Field(alias="docCount")
    created_time: str = Field(alias="createdTime")
    app_id: str = Field(alias="appId")
    is_debug: bool = Field(alias="isDebug")


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


class GetKnowledgeIDMsg(BaseModel):
    """GET /api/knowledge Result数据结构"""

    kb_id: str


class GetKnowledgeIDRsp(ResponseData):
    """GET /api/knowledge 返回数据结构"""

    result: GetKnowledgeIDMsg


class BaseAppOperationMsg(BaseModel):
    """基础应用操作Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")


class BaseAppOperationRsp(ResponseData):
    """基础应用操作返回数据结构"""

    result: BaseAppOperationMsg


class GetAppPropertyMsg(AppData):
    """GET /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    published: bool = Field(..., description="是否已发布")


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
    app_count: int = Field(..., alias="total", description="总页数")
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


class NodeServiceListMsg(BaseModel):
    """GET /api/flow/service result"""
    services: list[NodeServiceItem] = Field(..., description="服务列表",default=[])
class NodeServiceListRsp(ResponseData):
    """GET /api/flow/service 返回数据结构"""
    result: NodeServiceListMsg
class NodeMetaDataRsp(ResponseData):
    """GET /api/flow/service/node 返回数据结构"""
    result: NodeMetaDataItem

class FlowStructureGetMsg(BaseModel):
    """GET /api/flow result"""
    flow: FlowItem = Field(default=FlowItem())
    focus_point: PositionItem = Field(default=PositionItem())


class FlowStructureGetRsp(ResponseData):
    """GET /api/flow 返回数据结构"""
    result: FlowStructureGetMsg

class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""
    flow: FlowItem
    focus_point: PositionItem = Field(alias="focusPoint")

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
