# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from pydantic import BaseModel


# 问题相关 FastAPI 所需数据
class QuestionBlacklistRequest(BaseModel):
    question: str
    answer: str
    is_deletion: int


# 用户相关 FastAPI 所需数据
class UserBlacklistRequest(BaseModel):
    user_sub: str
    is_ban: int


# 举报相关 FastAPI 所需数据
class AbuseRequest(BaseModel):
    record_id: str
    reason: str


# 举报审核相关 FastAPI 所需数据
class AbuseProcessRequest(BaseModel):
    id: int
    is_deletion: int
