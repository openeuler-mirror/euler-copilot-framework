"""FastAPI 请求体

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from pydantic import BaseModel, Field

from apps.entities.appcenter import AppData
from apps.entities.flow_topology import EdgeItem, FlowItem, NodeItem, PositionItem
from apps.entities.task import RequestDataApp


class RequestDataFeatures(BaseModel):
    """POST /api/chat的features字段数据"""

    max_tokens: int = Field(default=8192, description="最大生成token数", ge=0)
    context_num: int = Field(default=5, description="上下文消息数量", le=10, ge=0)


class RequestData(BaseModel):
    """POST /api/chat 请求的总的数据结构"""

    question: str = Field(max_length=2000, description="用户输入")
    conversation_id: str = Field(default=None, alias="conversationId", description="会话ID")
    group_id: Optional[str] = Field(default=None, alias="groupId", description="群组ID")
    language: str = Field(default="zh", description="语言")
    files: list[str] = Field(default=[], description="文件列表")
    app: RequestDataApp = Field(default=[], description="应用列表")
    features: RequestDataFeatures = Field(description="消息功能设置")


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
    reason_type: list[str]


class AbuseProcessRequest(BaseModel):
    """POST /api/blacklist/abuse 请求数据结构"""

    id: str
    is_deletion: int


class CreateAppRequest(AppData):
    """POST /api/app 请求数据结构"""

    app_id: Optional[str] = Field(None, alias="appId", description="应用ID")


class ModFavAppRequest(BaseModel):
    """PUT /api/app/{appId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class ClientSessionData(BaseModel):
    """客户端Session信息"""

    session_id: Optional[str] = Field(default=None)


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
    is_like: bool = Field(...)
    dislike_reason: list[str] = Field(default=[], max_length=10)
    reason_link: str = Field(default=None, max_length=200)
    reason_description: str = Field(default=None, max_length=500)


class PostDomainData(BaseModel):
    """添加领域"""

    domain_name: str = Field(..., min_length=1, max_length=100)
    domain_description: str = Field(..., max_length=2000)


class PostKnowledgeIDData(BaseModel):
    """添加知识库"""

    kb_id: str


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem
    nodes: list[NodeItem]
    edges: list[EdgeItem]
    focus_point: PositionItem = Field(alias="focusPoint")
