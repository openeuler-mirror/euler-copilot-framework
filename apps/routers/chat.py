"""FastAPI 聊天接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import random
import traceback
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import ray
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.constants import LOGGER, SCHEDULER_REPLICAS
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import RequestData
from apps.entities.response_data import ResponseData
from apps.manager.appcenter import AppCenterManager
from apps.manager.blacklist import QuestionBlacklistManager, UserBlacklistManager
from apps.routers.mock import mock_data
from apps.scheduler.scheduler.context import save_data
from apps.service.activity import Activity

RECOMMEND_TRES = 5

router = APIRouter(
    prefix="/api",
    tags=["chat"],
)


async def chat_generator(post_body: RequestData, user_sub: str, session_id: str) -> AsyncGenerator[str, None]:
    """进行实际问答，并从MQ中获取消息"""
    try:
        await Activity.set_active(user_sub)

        # 敏感词检查
        word_check = ray.get_actor("words_check")
        if await word_check.check.remote(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            LOGGER.info(msg="问题包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 生成group_id
        group_id = str(uuid.uuid4()) if not post_body.group_id else post_body.group_id

        # 创建或还原Task
        task_pool = ray.get_actor("task")
        task = await task_pool.get_task.remote(session_id=session_id, post_body=post_body)
        task_id = task.record.task_id

        task.record.group_id = group_id
        post_body.group_id = group_id
        await task_pool.set_task.remote(task_id, task)

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue.remote()
        await queue.init.remote(task_id)  # type: ignore[attr-defined]

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        randnum = random.randint(0, SCHEDULER_REPLICAS - 1)  # noqa: S311
        scheduler_actor = ray.get_actor(f"scheduler_{randnum}")
        scheduler = scheduler_actor.run.remote(task_id, queue, user_sub, post_body)

        # 处理每一条消息
        async for event in queue.get.remote():  # type: ignore[attr-defined]
            content = await event
            if content[:6] == "[DONE]":
                break

            yield "data: " + content + "\n\n"

        # 等待Scheduler运行完毕
        result = await scheduler

        # 获取最终答案
        task = await task_pool.get_task.remote(task_id)
        answer_text = task.record.content.answer
        if not answer_text:
            LOGGER.error(msg="Answer is empty")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_sub)
            return

        # 对结果进行敏感词检查
        if await word_check.check.remote(answer_text) != 1:
            yield "data: [SENSITIVE]\n\n"
            LOGGER.info(msg="答案包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 创建新Record，存入数据库
        await save_data(task_id, user_sub, post_body, result.used_docs)

        yield "data: [DONE]\n\n"

    except Exception as e:
        LOGGER.error(msg=f"生成答案失败：{e!s}\n{traceback.format_exc()}")
        yield "data: [ERROR]\n\n"

    finally:
        await Activity.remove_active(user_sub)


@router.post("/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    post_body: RequestData,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> StreamingResponse:
    """LLM流式对话接口"""
    # 问题黑名单检测
    if not await QuestionBlacklistManager.check_blacklisted_questions(input_question=post_body.question):
        # 用户扣分
        await UserBlacklistManager.change_blacklisted_users(user_sub, -10)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="question is blacklisted")

    # 限流检查
    if await Activity.is_active(user_sub):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    if post_body.app and post_body.app.app_id:
        await AppCenterManager.update_recent_app(user_sub, post_body.app.app_id)
        if not post_body.app.flow_id:
            flow_id = await AppCenterManager.get_default_flow_id(post_body.app.app_id)
            post_body.app.flow_id = flow_id if flow_id else ""
        res = mock_data(
            appId=post_body.app.app_id,
            conversationId=post_body.conversation_id,
            flowId=post_body.app.flow_id,
            question=post_body.question,
        )
    else:
        res = chat_generator(post_body, user_sub, session_id)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def stop_generation(user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """停止生成"""
    await Activity.remove_active(user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="stop generation success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )
