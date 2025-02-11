"""FastAPI 聊天接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import traceback
import uuid
from collections.abc import AsyncGenerator
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
from apps.entities.response_data import ResponseData
from apps.manager import (
    QuestionBlacklistManager,
    TaskManager,
    UserBlacklistManager,
)
from apps.manager.appcenter import AppCenterManager
from apps.scheduler.scheduler import Scheduler
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
        if await WordsCheck.check(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            LOGGER.info(msg="问题包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 生成group_id
        group_id = str(uuid.uuid4()) if not post_body.group_id else post_body.group_id

        # 创建或还原Task
        task = await TaskManager.get_task(session_id=session_id, post_body=post_body)
        task_id = task.record.task_id

        task.record.group_id = group_id
        post_body.group_id = group_id
        await TaskManager.set_task(task_id, task)

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init(task_id, enable_heartbeat=True)

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        scheduler = Scheduler(task_id, queue)
        scheduler_task = asyncio.create_task(scheduler.run(user_sub, session_id, post_body))

        # 处理每一条消息
        async for event in queue.get():
            if event[:6] == "[DONE]":
                break

            yield "data: " + event + "\n\n"

        # 等待Scheduler运行完毕
        await asyncio.gather(scheduler_task)

        # 获取最终答案
        task = await TaskManager.get_task(task_id)
        answer_text = task.record.content.answer
        if not answer_text:
            LOGGER.error(msg="Answer is empty")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_sub)
            return

        # 对结果进行敏感词检查
        if await WordsCheck.check(answer_text) != 1:
            yield "data: [SENSITIVE]\n\n"
            LOGGER.info(msg="答案包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 创建新Record，存入数据库
        await scheduler.save_state(user_sub, post_body)
        # 保存Task，从task_map中删除task
        await TaskManager.save_task(task_id)

        yield "data: [DONE]\n\n"

    except Exception as e:
        LOGGER.error(msg=f"生成答案失败：{e!s}\n{traceback.format_exc()}")
        yield "data: [ERROR]\n\n"

    finally:
        if scheduler_task:
            scheduler_task.cancel()
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
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="stop generation success",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
