# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""黑名单相关数据结构"""

import uuid

from pydantic import BaseModel

from apps.schemas.response_data import ResponseData


class QuestionBlacklistRequest(BaseModel):
    """POST /api/blacklist/question 请求数据结构"""

    id: str
    question: str
    answer: str
    is_deletion: int


class UserBlacklistRequest(BaseModel):
    """POST /api/blacklist/user 请求数据结构"""

    user_id: str
    is_ban: int


class AbuseRequest(BaseModel):
    """POST /api/blacklist/complaint 请求数据结构"""

    record_id: uuid.UUID
    reason: str
    reason_type: str


class AbuseProcessRequest(BaseModel):
    """POST /api/blacklist/abuse 请求数据结构"""

    id: uuid.UUID
    is_deletion: int


class BlacklistSchema(BaseModel):
    """黑名单 Pydantic 数据结构"""

    id: int
    """主键ID"""
    recordId: uuid.UUID  # noqa: N815
    """关联的问答对ID"""
    question: str
    """黑名单问题"""
    answer: str | None
    """应做出的固定回答"""
    isAudited: bool  # noqa: N815
    """黑名单是否生效"""
    reasonType: str  # noqa: N815
    """举报类型"""
    reason: str
    """举报原因"""
    updatedAt: str  # noqa: N815
    """更新时间"""

    class Config:
        """Pydantic 配置"""

        from_attributes = True


class BlacklistedUser(BaseModel):
    """被封禁用户的数据结构"""

    user_id: str
    user_name: str


class GetBlacklistUserMsg(BaseModel):
    """GET /api/blacklist/user Result数据结构"""

    users: list[BlacklistedUser]


class GetBlacklistUserRsp(ResponseData):
    """GET /api/blacklist/user 返回数据结构"""

    result: GetBlacklistUserMsg


class GetBlacklistQuestionMsg(BaseModel):
    """GET /api/blacklist/question Result数据结构"""

    question_list: list[BlacklistSchema]


class GetBlacklistQuestionRsp(ResponseData):
    """GET /api/blacklist/question 返回数据结构"""

    result: GetBlacklistQuestionMsg
