"""FastAPI 黑名单相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import get_user, verify_user
from apps.entities.request_data import (
    AbuseProcessRequest,
    AbuseRequest,
    QuestionBlacklistRequest,
    UserBlacklistRequest,
)
from apps.entities.response_data import (
    GetBlacklistQuestionMsg,
    GetBlacklistQuestionRsp,
    GetBlacklistUserMsg,
    GetBlacklistUserRsp,
    ResponseData,
)
from apps.manager.blacklist import (
    AbuseManager,
    QuestionBlacklistManager,
    UserBlacklistManager,
)

router = APIRouter(
    prefix="/api/blacklist",
    tags=["blacklist"],
    dependencies=[Depends(verify_user)],
)
PAGE_SIZE = 20
MAX_CREDIT = 100


@router.get("/user", response_model=GetBlacklistUserRsp)
async def get_blacklist_user(page: int = 0):  # noqa: ANN201
    """获取黑名单用户"""
    # 计算分页
    user_list = await UserBlacklistManager.get_blacklisted_users(
        PAGE_SIZE,
        page * PAGE_SIZE,
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistUserRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistUserMsg(user_subs=user_list),
    ).model_dump(exclude_none=True, by_alias=True))


@router.post("/user", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def change_blacklist_user(request: UserBlacklistRequest):  # noqa: ANN201
    """操作黑名单用户"""
    # 拉黑用户
    if request.is_ban:
        result = await UserBlacklistManager.change_blacklisted_users(
            request.user_sub,
            -MAX_CREDIT,
        )
    # 解除拉黑
    else:
        result = await UserBlacklistManager.change_blacklisted_users(
            request.user_sub,
            MAX_CREDIT,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Change user blacklist error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))

@router.get("/question", response_model=GetBlacklistQuestionRsp)
async def get_blacklist_question(page: int = 0):  # noqa: ANN201
    """获取黑名单问题

    目前情况下，先直接输出问题，不做用户类型校验
    """
    # 计算分页
    question_list = await QuestionBlacklistManager.get_blacklisted_questions(
        PAGE_SIZE,
        page * PAGE_SIZE,
        is_audited=True,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistQuestionRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistQuestionMsg(question_list=question_list),
    ).model_dump(exclude_none=True, by_alias=True))

@router.post("/question", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def change_blacklist_question(request: QuestionBlacklistRequest):  # noqa: ANN201
    """黑名单问题检测或操作"""
    # 删问题
    if request.is_deletion:
        result = await QuestionBlacklistManager.change_blacklisted_questions(
            request.id,
            request.question,
            request.answer,
            is_deletion=True,
        )
    else:
        # 改问题
        result = await QuestionBlacklistManager.change_blacklisted_questions(
            request.id,
            request.question,
            request.answer,
            is_deletion=False,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Modify question blacklist error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@router.post("/complaint", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def abuse_report(request: AbuseRequest, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """用户实施举报"""
    result = await AbuseManager.change_abuse_report(
        user_sub,
        request.record_id,
        request.reason_type,
        request.reason,
    )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Report abuse complaint error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@router.get("/abuse", response_model=GetBlacklistQuestionRsp)
async def get_abuse_report(page: int = 0):  # noqa: ANN201
    """获取待审核的问答对"""
    # 此处前端需记录ID
    result = await QuestionBlacklistManager.get_blacklisted_questions(
        PAGE_SIZE,
        page * PAGE_SIZE,
        is_audited=False,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistQuestionRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistQuestionMsg(question_list=result),
    ).model_dump(exclude_none=True, by_alias=True))

@router.post("/abuse", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def change_abuse_report(request: AbuseProcessRequest):  # noqa: ANN201
    """对被举报问答对进行操作"""
    if request.is_deletion:
        result = await AbuseManager.audit_abuse_report(
            request.id,
            is_deletion=True,
        )
    else:
        result = await AbuseManager.audit_abuse_report(
            request.id,
            is_deletion=False,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Audit abuse question error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
