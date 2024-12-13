# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from fastapi import APIRouter, Depends, Response, status

from apps.dependency.user import verify_user, get_user
from apps.dependency.csrf import verify_csrf_token
from apps.entities.blacklist import (
    AbuseProcessRequest,
    AbuseRequest,
    QuestionBlacklistRequest,
    UserBlacklistRequest,
)
from apps.entities.response_data import ResponseData
from apps.manager.blacklist import (
    AbuseManager,
    QuestionBlacklistManager,
    UserBlacklistManager,
)
from apps.models.mysql import User

router = APIRouter(
    prefix="/api/blacklist",
    tags=["blacklist"],
    dependencies=[Depends(verify_user)],
)

PAGE_SIZE = 20
MAX_CREDIT = 100


# 通用返回函数
def check_result(result: any, response: Response, error_msg: str) -> ResponseData:
    if result is None:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=error_msg,
            result={}
        )
    else:
        if isinstance(result, dict):
            response.status_code = status.HTTP_200_OK
            return ResponseData(
                code=status.HTTP_200_OK,
                message="ok",
                result=result
            )
        else:
            response.status_code = status.HTTP_200_OK
            return ResponseData(
                code=status.HTTP_200_OK,
                message="ok",
                result={"value": result}
            )

# 用户实施举报
@router.post("/complaint", dependencies=[Depends(verify_csrf_token)])
async def abuse_report(request: AbuseRequest, response: Response, user: User = Depends(get_user)):
    result = AbuseManager.change_abuse_report(
        user.user_sub,
        request.record_id,
        request.reason
    )
    return check_result(result, response, "Report abuse complaint error.")
