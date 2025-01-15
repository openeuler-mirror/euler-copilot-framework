"""MongoDB中的数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from apps.constants import NEW_CHAT


class Blacklist(BaseModel):
    """黑名单

    Collection: blacklist
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    question: str
    answer: str
    is_audited: bool = False
    reason_type: list[str] = []
    reason: Optional[str] = None
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class UserDomainData(BaseModel):
    """用户领域数据"""

    name: str
    count: int


class User(BaseModel):
    """用户信息

    Collection: user
    外键：user - conversation
    """

    id: str = Field(alias="_id")
    last_login: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
    is_active: bool = False
    is_whitelisted: bool = False
    credit: int = 100
    api_key: Optional[str] = None
    kb_id: Optional[str] = None
    conversations: list[str] = []
    domains: list[UserDomainData] = []


class Conversation(BaseModel):
    """对话信息

    Collection: conversation
    外键：conversation - task, document, record_group
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    title: str = NEW_CHAT
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
    tasks: list[str] = []
    unused_docs: list[str] = []
    record_groups: list[str] = []


class Document(BaseModel):
    """文件信息

    Collection: document
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    name: str
    type: str
    size: float
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
    conversation_id: str


class Audit(BaseModel):
    """审计日志

    Collection: audit
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: Optional[str] = None
    http_method: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
    module: str
    client_ip: Optional[str] = None
    message: str


class RecordMetadata(BaseModel):
    """Record表子项：Record的元信息"""

    input_tokens: int
    output_tokens: int
    time: float
    feature: dict[str, Any] = {}


class RecordContent(BaseModel):
    """Record表子项：Record加密前的数据结构"""

    question: str
    answer: str
    data: dict[str, Any] = {}


class RecordComment(BaseModel):
    """Record表子项：Record的评论信息"""

    is_liked: bool
    feedback_type: list[str]
    feedback_link: str
    feedback_content: str
    feedback_time: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class Record(BaseModel):
    """问答"""

    record_id: str
    user_sub: str
    data: str
    key: dict[str, Any] = {}
    flow: list[str] = Field(description="[运行后修改]与Record关联的FlowHistory的ID", default=[])
    facts: list[str] = Field(description="[运行后修改]与Record关联的事实信息", default=[])
    comment: Optional[RecordComment] = None
    metadata: Optional[RecordMetadata] = None
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class RecordGroupDocument(BaseModel):
    """RecordGroup关联的文件"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    associated: Literal["question", "answer"]


class RecordGroup(BaseModel):
    """问答组

    多次重新生成的问答都是一个问答组
    Collection: record_group
    外键：record_group - document
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    records: list[Record] = []
    docs: list[RecordGroupDocument] = []    # 问题不变，所用到的文档不变
    conversation_id: str
    task_id: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class Domain(BaseModel):
    """领域信息

    Collection: domain
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    definition: str
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))
