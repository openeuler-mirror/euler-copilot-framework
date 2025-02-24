"""User用户信息数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    """用户信息数据结构"""

    user_sub: str = Field(alias="userSub", default="")
    user_name: str = Field(alias="userName", default="")
