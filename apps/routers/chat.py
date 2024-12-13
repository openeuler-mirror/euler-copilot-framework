# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from apps.common.wordscheck import WordsCheck
from apps.dependency.csrf import verify_csrf_token
from apps.dependency.limit import moving_window_limit
from apps.dependency.user import get_session, get_user, verify_user
from apps.entities.request_data import RequestData
from apps.entities.response_data import ResponseData
from apps.entities.user import User
from apps.manager.blacklist import (
    QuestionBlacklistManager,
    UserBlacklistManager,
)
from apps.manager.conversation import ConversationManager
from apps.manager.record import RecordManager
from apps.scheduler.scheduler import Scheduler
from apps.service import RAG, Activity, ChatSummary, Suggestion
from apps.service.history import History

logger = logging.getLogger('gunicorn.error')
RECOMMEND_TRES = 5

router = APIRouter(
    prefix="/api",
    tags=["chat"]
)


async def generate_content_stream(user_sub, session_id: str, post_body: RequestData):
    if not Activity.is_active(user_sub):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    try:
        if await WordsCheck.check(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            return
    except Exception as e:
        logger.error(msg="敏感词检查失败：{}".format(str(e)))
        yield "data: [ERROR]\n\n"
        Activity.remove_active(user_sub)
        return

    try:
        summary = History.get_summary(post_body.conversation_id)
        group_id, history = History.get_history_messages(post_body.conversation_id, post_body.record_id)
    except Exception as e:
        logger.error("获取历史记录失败！{}".format(str(e)))
        yield "data: [ERROR]\n\n"
        Activity.remove_active(user_sub)
        return

    # 找出当前执行的Flow ID
    if post_body.user_selected_flow is None:
        logger.info("Executing: {}".format(post_body.user_selected_flow))
        flow_id = await Scheduler.choose_flow(
            question=post_body.question,
            user_selected_plugins=post_body.user_selected_plugins
        )
    else:
        flow_id = post_body.user_selected_flow

    # 如果flow_id还是None：调用智能问答
    full_answer = ""
    if flow_id is None:
        logger.info("Executing: KnowledgeBase")
        async for line in RAG.get_rag_result(
            user_sub,
            post_body.question,
            post_body.language,
            history
        ):
            if Activity.is_active(user_sub):
                yield line
                try:
                    data = json.loads(line[6:])["content"]
                    full_answer += data
                except Exception:
                    continue

    # 否则：执行特定Flow
    else:
        logger.info("Executing: {}".format(flow_id))
        async for line in Scheduler.run_certain_flow(
            user_selected_flow=flow_id,
            question=post_body.question,
            files=post_body.files,
            context=summary,
            session_id=session_id
        ):
            if Activity.is_active(user_sub):
                yield line
                try:
                    data = json.loads(line[6:])["content"]
                    full_answer += data
                except Exception:
                    continue

    # 对结果进行敏感词检查
    if await WordsCheck.check(full_answer) != 1:
        yield "data: [SENSITIVE]\n\n"
        return
    # 存入数据库，更新Summary
    record_id = str(uuid.uuid4().hex)
    RecordManager().insert_encrypted_data(
        post_body.conversation_id,
        record_id,
        group_id,
        user_sub,
        post_body.question,
        full_answer
    )
    Suggestion.update_user_domain(user_sub, post_body.question, full_answer)
    new_summary = await ChatSummary.generate_chat_summary(
        last_summary=summary, question=post_body.question, answer=full_answer)
    del summary
    ConversationManager.update_summary(post_body.conversation_id, new_summary)
    yield 'data: {"qa_record_id": "' + record_id + '"}\n\n'

    if len(post_body.user_selected_plugins) != 0:
        # 如果选择了插件，走Flow推荐
        suggestions = await Scheduler.plan_next_flow(
            question=post_body.question,
            summary=new_summary,
            user_selected_plugins=post_body.user_selected_plugins,
            current_flow_name=flow_id
        )
    else:
        # 如果未选择插件，不走Flow推荐
        suggestions = []

    # 限制推荐个数
    if len(suggestions) < RECOMMEND_TRES:
        domain_suggestions = Suggestion.generate_suggestions(
            post_body.conversation_id, summary=new_summary, question=post_body.question, answer=full_answer)
        for i in range(min(RECOMMEND_TRES - len(suggestions), 3)):
            suggestions.append(domain_suggestions[i])
    yield 'data: {"search_suggestions": ' + json.dumps(suggestions, ensure_ascii=False) + '}' + '\n\n'

    # 删除活跃标识
    del new_summary
    if not Activity.is_active(user_sub):
        return

    yield 'data: [DONE]\n\n'
    Activity.remove_active(user_sub)


async def natural_language_post_func(post_body: RequestData, user: User, session_id: str):
    user_sub = user.user_sub
    try:
        headers = {
            "X-Accel-Buffering": "no"
        }
        # 问题黑名单检测
        if QuestionBlacklistManager.check_blacklisted_questions(input_question=post_body.question):
            res = generate_content_stream(user_sub, session_id, post_body)
        else:
            # 用户扣分
            UserBlacklistManager.change_blacklisted_users(user_sub, -10)
            res_data = ['data: [SENSITIVE]' + '\n\n']
            res = iter(res_data)

        response = StreamingResponse(
            content=res,
            media_type="text/event-stream",
            headers=headers
        )
        return response
    except Exception as ex:
        logger.info(f"Get stream answer failed due to error: {ex}")
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.post("/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
@moving_window_limit
async def natural_language_post(
    post_body: RequestData,
    user: User = Depends(get_user),
    session_id: str = Depends(get_session)
):
    return await natural_language_post_func(post_body, user, session_id)


@router.post("/stop", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def stop_generation(user: User = Depends(get_user)):
    user_sub = user.user_sub
    Activity.remove_active(user_sub)
    return ResponseData(
        code=status.HTTP_200_OK,
        message="stop generation success",
        result={}
    )
