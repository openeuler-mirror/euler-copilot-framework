# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from typing import List, Optional

from pydantic import BaseModel, Field


class RequestData(BaseModel):
    question: str = Field(..., max_length=2000)
    language: Optional[str] = Field(default="zh")
    conversation_id: str = Field(..., min_length=32, max_length=32)
    record_id: Optional[str] = Field(default=None)
    user_selected_plugins: List[str] = Field(default=[])
    user_selected_flow: Optional[str] = Field(default=None)
    files: Optional[List[str]] = Field(default=None)
    flow_id: Optional[str] = Field(default=None)


class ClientChatRequestData(BaseModel):
    session_id: str = Field(..., min_length=32, max_length=32)
    question: str = Field(..., max_length=2000)
    language: Optional[str] = Field(default="zh")
    conversation_id: str = Field(..., min_length=32, max_length=32)
    record_id: Optional[str] = Field(default=None)
    user_selected_plugins: List[str] = Field(default=[])
    user_selected_flow: Optional[str] = Field(default=None)
    files: Optional[List[str]] = Field(default=None)
    flow_id: Optional[str] = Field(default=None)


class ClientSessionData(BaseModel):
    session_id: Optional[str] = Field(default=None)


class ModifyConversationData(BaseModel):
    title: str = Field(..., min_length=1, max_length=2000)


class ModifyRevisionData(BaseModel):
    revision_num: str = Field(..., min_length=5, max_length=5)


class DeleteConversationData(BaseModel):
    conversation_list: list[str] = Field(...)


class AddCommentData(BaseModel):
    record_id: str = Field(..., min_length=32, max_length=32)
    is_like: bool = Field(...)
    dislike_reason: str = Field(default=None, max_length=100)
    reason_link: str = Field(default=None, max_length=200)
    reason_description: str = Field(
        default=None, max_length=500)


class AddDomainData(BaseModel):
    domain_name: str = Field(..., min_length=1, max_length=100)
    domain_description: str = Field(..., max_length=2000)
