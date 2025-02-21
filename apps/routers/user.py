
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.common.wordscheck import WordsCheck
from apps.constants import LOGGER
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import RequestData
from apps.entities.response_data import ResponseData, UserGetMsp, UserGetRsp
from apps.entities.user import UserInfo
from apps.manager.appcenter import AppCenterManager
from apps.scheduler.scheduler import Scheduler
from apps.service.activity import Activity
from apps.manager.user import UserManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)

@router.get("", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> JSONResponse:
    """查询所有用户接口"""
    user_list = await UserManager.get_all_user_sub()
    user_info_list = []
    for user in user_list:
        # user_info = await UserManager.get_userinfo_by_user_sub(user) 暂时不需要查询user_name
        if user == user_sub:
            continue
        info = UserInfo(
                userName=user,
                userSub=user,
            )
        user_info_list.append(info)

    return JSONResponse(status_code=status.HTTP_200_OK, content=UserGetRsp(
        code=status.HTTP_200_OK,
        message="节点元数据详细信息获取成功",
        result=UserGetMsp(userInfoList=user_info_list),
    ).model_dump(exclude_none=True, by_alias=True))
