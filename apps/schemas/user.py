# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""User用户信息数据结构"""

from pydantic import BaseModel, Field

from .response_data import ResponseData


class UserListItem(BaseModel):
    """用户信息数据结构"""

    user_sub: str = Field(alias="userSub", default="")
    user_name: str = Field(alias="userName", default="")


class UserInfoMsg(BaseModel):
    """GET /api/user Result数据结构"""

    id: int
    user_name: str = Field(alias="userName", default="")
    is_admin: bool = Field(alias="isAdmin", default=False)
    personal_token: str = Field(alias="personalToken", default="")
    auto_execute: bool = Field(alias="autoExecute", default=False)


class UserInfoRsp(ResponseData):
    """GET /api/user Result数据结构"""

    result: UserInfoMsg


class UserListMsg(BaseModel):
    """GET /api/user/list Result数据结构"""

    total: int = Field(default=0)
    user_info_list: list[UserListItem] = Field(alias="userInfoList", default=[])


class UserListRsp(ResponseData):
    """GET /api/user/list 返回数据结构"""

    result: UserListMsg
