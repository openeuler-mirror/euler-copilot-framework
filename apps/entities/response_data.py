"""FastAPI 返回数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.collection import Blacklist, Document, NodeMetaData
from apps.entities.enum_var import DocumentStatus
from apps.entities.flow import EdgeItem, FlowItem, NodeItem, PositionItem
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


class NodeMetaDataItem(BaseModel):
    """GET /api/flow/node/metadata 单个节点元数据结构"""
    api_id: str = Field(alias="apiId")
    name:str
    type:str
    created_at: str= Field(alias="createdAt")
class ServiceNodeMetaDatasItem(BaseModel):
    """GET /api/flow/node/metadata 服务与服务下节点元数据结构"""
    service_id:str=Field(alias="serviceId")
    name:str
    type:str
    node_meta_datas:list[NodeMetaDataItem]=Field(alias="nodeMetaData",default=[])
    created_at: str= Field(alias="createdAt")
class NodeMetaDataListMsg(ResponseData):
    services:list[ServiceNodeMetaDatasItem]
class NodeMetaDataListRsp(ResponseData):
    """GET /api/flow/node/metadata 返回数据结构"""
    result:NodeMetaDataListMsg


class FlowStructureGetMsg(BaseModel):
    """GET /api/flow/{flowId} result"""
    flow:FlowItem
    nodes:list[NodeItem]
    edges:list[EdgeItem]
    focus_point:PositionItem=Field(alias="focusPoint")

class FlowStructureGetRsp(BaseModel):
    """GET /api/flow/{flowId} 返回数据结构"""
    result:FlowStructureGetMsg
class FlowStructurePutMsg(BaseModel):
    """PUT /api/flow result"""
    flow_id:str=Field(alias="flowId")
class FlowStructurePutRsp(ResponseData):
    """PUT /api/flow 返回数据结构"""
    flow_id:str=Field(alias="flowId")

class FlowStructureDeleteMsg(BaseModel):
    """DELETE /api/flow/{flowId} result"""
    flow_id:str=Field(alias="flowId")
class FlowStructureDeleteRsp(ResponseData):
    """DELETE /api/flow/{flowId} 返回数据结构"""
    flow_id:str=Field(alias="flowId")

class NodeParameterItem(BaseModel):
    parameter_id:str=Field(alias="parameterId")
    content:str
    updated_at: str= Field(alias="updatedAt")
class NodeParameterGetMsg(BaseModel):
    """GET /api/flow/node/parameter result"""
    node_id:str=Field(alias="nodeId")
    parameter:NodeParameterItem
class NodeParameterGetRsp(ResponseData):
    """GET /api/flow/node/parameter 返回数据结构"""
    result:NodeParameterGetMsg
class NodeParameterListMsg(BaseModel):
    """GET /api/flow/node/parameter/history result"""
    node_id:str=Field(alias="nodeId")
    parameter_history:list[NodeParameterItem]=Field(alias="parameterHistory")
class NodeParameterListRsp(ResponseData):
    """GET /api/flow/node/parameter/history 返回数据结构"""
    result:NodeParameterListMsg

class NodeParameterPutMsg(BaseModel):
    """PUT /api/flow/node/parameter result"""
    node_id:str=Field(alias="nodeId")
    parameter_id:str=Field(alias="parameterId")
class NodeParameterPutRsp(ResponseData):
    """PUT /api/flow/node/parameter 返回数据结构"""
    result:NodeParameterPutMsg
