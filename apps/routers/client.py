# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import Optional

from fastapi import APIRouter, Depends, status
from starlette.requests import HTTPConnection

from apps.dependency.limit import moving_window_limit
from apps.dependency.user import get_user_by_api_key, verify_api_key
from apps.entities.plugin import PluginListData
from apps.entities.request_data import ClientChatRequestData, ClientSessionData, RequestData
from apps.entities.response_data import ResponseData
from apps.entities.user import User
from apps.manager.session import SessionManager
from apps.routers.chat import natural_language_post_func
from apps.routers.conversation import add_conversation_func
from apps.scheduler.pool.pool import Pool
from apps.service import Activity

router = APIRouter(
    prefix="/api/client",
    tags=["client"]
)


@router.post("/session", response_model=ResponseData)
async def get_session_id(
    request: HTTPConnection,
    post_body: ClientSessionData,
    user: User = Depends(get_user_by_api_key)
):
    session_id: Optional[str] = post_body.session_id
    if session_id and not SessionManager.verify_user(session_id) or not session_id:
        return ResponseData(
            code=status.HTTP_200_OK, message="gen new session id success", result={
                "session_id": SessionManager.create_session(request.client.host, extra_keys={
                    "user_sub": user.user_sub
                })
            }
        )
    return ResponseData(
        code=status.HTTP_200_OK, message="verify session id success", result={"session_id": session_id}
    )


@router.get("/plugin", response_model=PluginListData, dependencies=[Depends(verify_api_key)])
async def get_plugin_list():
    return PluginListData(code=status.HTTP_200_OK, message="success", result=Pool().get_plugin_list())


@router.post("/conversation", response_model=ResponseData)
async def add_conversation(user: User = Depends(get_user_by_api_key)):
    return await add_conversation_func(user)


@router.post("/chat")
@moving_window_limit
async def natural_language_post(post_body: ClientChatRequestData, user: User = Depends(get_user_by_api_key)):
    body: RequestData = RequestData(
        question=post_body.question,
        language=post_body.language,
        conversation_id=post_body.conversation_id,
        record_id=post_body.record_id,
        user_selected_plugins=post_body.user_selected_plugins,
        user_selected_flow=post_body.user_selected_flow,
        files=post_body.files,
        flow_id=post_body.flow_id,
    )
    session_id: str = post_body.session_id
    return await natural_language_post_func(body, user, session_id)


@router.post("/stop", response_model=ResponseData)
async def stop_generation(user: User = Depends(get_user_by_api_key)):
    user_sub = user.user_sub
    Activity.remove_active(user_sub)
    return ResponseData(code=status.HTTP_200_OK, message="stop generation success", result={})
