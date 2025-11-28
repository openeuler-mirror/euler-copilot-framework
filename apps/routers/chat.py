# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 聊天接口"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.dependency import verify_personal_token, verify_session
from apps.models import ExecutorStatus
from apps.scheduler.scheduler import Scheduler
from apps.schemas.request_data import RequestData
from apps.schemas.response_data import ResponseData
from apps.services.activity import Activity
from apps.services.flow import FlowManager

_logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["chat"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)

async def chat_generator(post_body: RequestData, user_id: str, auth_header: str) -> AsyncGenerator[str, None]:
    """进行实际问答，并从MQ中获取消息"""
    try:
        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init()

        # 1. 先初始化 Scheduler（确保初始化成功）
        scheduler = Scheduler()
        await scheduler.init(queue, post_body, user_id, auth_header)

        # 2. Scheduler初始化成功后，再设置用户处于活动状态
        await Activity.set_active(user_id)
        _logger.info(f"[Chat] 用户是否活跃: {await Activity.can_active(user_id)}")

        # 3. 最后判断并运行 Executor
        scheduler_task = asyncio.create_task(scheduler.run())

        # 处理每一条消息
        async for content in queue.get():
            if content[:6] == "[DONE]":
                break

            yield "data: " + content + "\n\n"
        # 等待Scheduler运行完毕
        await scheduler_task

        # 获取最终答案
        task = scheduler.task
        if task.state and task.state.executorStatus == ExecutorStatus.ERROR:
            _logger.error("[Chat] 生成答案失败")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_id)
            return

        if post_body.app and post_body.app.flow_id:
            await FlowManager.update_flow_debug_by_app_and_flow_id(
                post_body.app.app_id,
                post_body.app.flow_id,
                debug=True,
            )

        yield "data: [DONE]\n\n"

    except Exception:
        _logger.exception("[Chat] 生成答案失败")
        yield "data: [ERROR]\n\n"

    finally:
        await Activity.remove_active(user_id)


@router.post("/chat")
async def chat(request: Request, post_body: RequestData) -> StreamingResponse:
    """LLM流式对话接口"""
    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "")
    user_id = request.state.user_id

    res = chat_generator(post_body, user_id, auth_header)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop", response_model=ResponseData)
async def stop_generation(request: Request) -> JSONResponse:
    """停止生成"""
    await Activity.remove_active(request.state.user_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="stop generation success",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
