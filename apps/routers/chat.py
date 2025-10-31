# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 聊天接口"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.common.wordscheck import words_check
from apps.dependency import verify_personal_token, verify_session
from apps.models import ExecutorStatus
from apps.scheduler.scheduler import Scheduler
from apps.schemas.request_data import RequestData
from apps.schemas.response_data import ResponseData
from apps.services.activity import Activity
from apps.services.blacklist import QuestionBlacklistManager, UserBlacklistManager
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

async def chat_generator(post_body: RequestData, user_id: str, session_id: str) -> AsyncGenerator[str, None]:
    """进行实际问答，并从MQ中获取消息"""
    try:
        await Activity.set_active(user_id)

        # 敏感词检查
        if await words_check.check(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            _logger.info("[Chat] 问题包含敏感词！")
            await Activity.remove_active(user_id)
            return

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init()

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        scheduler = Scheduler()
        await scheduler.init(queue, post_body, user_id)
        _logger.info(f"[Chat] 用户是否活跃: {await Activity.is_active(user_id)}")
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

        # 对结果进行敏感词检查
        if await words_check.check(task.runtime.fullAnswer) != 1:
            yield "data: [SENSITIVE]\n\n"
            _logger.info("[Chat] 答案包含敏感词！")
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
    session_id = request.state.session_id
    user_id = request.state.user_id
    # 问题黑名单检测
    if (post_body.question is not None) and (
        not await QuestionBlacklistManager.check_blacklisted_questions(input_question=post_body.question)
    ):
        # 用户扣分
        await UserBlacklistManager.change_blacklisted_users(user_id, -10)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="question is blacklisted")

    res = chat_generator(post_body, user_id, session_id)
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
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="stop generation success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )
