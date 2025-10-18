# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Session相关数据结构"""

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    """
    Session

    collection: session
    """

    id: str = Field(alias="_id")
    ip: str
    user_sub: str | None = None
    user_name: str | None = None
    nonce: str | None = None
    expired_at: datetime
