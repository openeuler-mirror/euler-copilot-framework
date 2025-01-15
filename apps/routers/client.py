"""FastAPI Shell端对接相关接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection

from apps.dependency.user import get_user_by_api_key
from apps.entities.request_data import ClientSessionData
from apps.entities.response_data import (
    PostClientSessionMsg,
    PostClientSessionRsp,
    ResponseData,
)
from apps.manager.session import SessionManager

router = APIRouter(
    prefix="/api/client",
    tags=["client"],
)


@router.post("/session", response_model=PostClientSessionRsp, responses={
    status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
})
async def get_session_id(  # noqa: ANN201
    request: HTTPConnection,
    post_body: ClientSessionData,
    user_sub: Annotated[str, Depends(get_user_by_api_key)],
):
    """获取客户端会话ID"""
    session_id: Optional[str] = post_body.session_id
    if not request.client:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="client not found",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    if (session_id and not await SessionManager.verify_user(session_id)) or not session_id:
        return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
            code=status.HTTP_200_OK,
            message="gen new session id success",
            result={
                "session_id": await SessionManager.create_session(request.client.host, extra_keys={
                    "user_sub": user_sub,
                }),
            },
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=PostClientSessionRsp(
        code=status.HTTP_200_OK,
        message="verify session id success",
        result=PostClientSessionMsg(
            session_id=session_id,
        ),
    ).model_dump(exclude_none=True, by_alias=True))
