"""FastAPI 返回数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from apps.entities.collection import Blacklist, Document
from apps.entities.enum import DocumentStatus
from apps.entities.plugin import PluginData
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

class GetPluginListMsg(BaseModel):
    """GET /api/plugin Result数据结构"""

    plugins: list[PluginData]

class GetPluginListRsp(ResponseData):
    """GET /api/plugin 返回数据结构"""

    result: GetPluginListMsg


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

    conversation_id: str
    title: str
    doc_count: int
    created_time: str

class ConversationListMsg(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversations: list[ConversationListItem]


class ConversationListRsp(ResponseData):
    """GET /api/conversation 返回数据结构"""

    result: ConversationListMsg


class AddConversationMsg(BaseModel):
    """POST /api/conversation Result数据结构"""

    conversation_id: str


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
