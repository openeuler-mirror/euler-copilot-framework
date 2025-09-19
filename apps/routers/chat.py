# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 聊天接口"""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.common.wordscheck import WordsCheck
from apps.dependency import get_session, get_user
from apps.scheduler.scheduler import Scheduler
from apps.scheduler.scheduler.context import save_data
from apps.schemas.request_data import RequestData
from apps.schemas.response_data import ResponseData
from apps.schemas.task import Task
from apps.services.activity import Activity
from apps.services.blacklist import QuestionBlacklistManager, UserBlacklistManager
from apps.services.flow import FlowManager
from apps.services.task import TaskManager
from apps.services.appcenter import AppCenterManager
from apps.scheduler.variable.pool_manager import get_pool_manager
from apps.scheduler.variable.type import VariableType, VariableScope

RECOMMEND_TRES = 5
logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["chat"],
)


async def check_required_file_variables(flow_id: str, conversation_id: str, user_sub: str) -> list[str]:
    """检查必填文件变量是否已上传
    
    Args:
        flow_id: 工作流ID
        conversation_id: 对话ID
        user_sub: 用户ID
        
    Returns:
        list[str]: 缺失的必填文件变量名称列表
    """
    try:
        pool_manager = await get_pool_manager()
        missing_variables = []
        
        # 获取对话变量模板（从flow pool获取）
        flow_pool = await pool_manager.get_flow_pool(flow_id)
        if not flow_pool:
            logger.warning(f"无法获取工作流池: flow_id={flow_id}")
            return missing_variables
            
        # 获取所有对话变量模板
        conversation_templates = await flow_pool.list_conversation_templates()
        required_file_variables = []
        
        logger.info(f"检查工作流 {flow_id} 中的对话变量模板，总数: {len(conversation_templates)}")
        
        # 筛选出必填的文件类型变量
        for template in conversation_templates:
            logger.info(f"检查变量: {template.metadata.name}, 类型: {template.metadata.var_type}, 作用域: {template.metadata.scope}")
            if (template.metadata.scope == VariableScope.CONVERSATION and 
                template.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]):
                
                logger.info(f"发现文件类型变量: {template.metadata.name}, 值: {template.value}")
                # 检查是否为必填
                if isinstance(template.value, dict) and template.value.get("required", False):
                    required_file_variables.append(template.metadata.name)
                    logger.info(f"变量 {template.metadata.name} 标记为必填")
                else:
                    logger.info(f"变量 {template.metadata.name} 不是必填或值格式不正确")
        
        if not required_file_variables:
            # 没有必填的文件变量
            return missing_variables
            
        logger.info(f"发现必填文件变量: {required_file_variables}")
        
        # 获取实际的对话变量池
        conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
        if not conversation_pool:
            # 🔑 重要修复：如果对话池不存在，尝试创建它
            # 这种情况可能发生在某些边界场景下
            try:
                # 获取flow_id
                from apps.services.document import DocumentManager
                flow_id = await DocumentManager._get_flow_id_for_conversation(conversation_id)
                if flow_id:
                    conversation_pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
                    logger.info(f"为检查创建了对话池: {conversation_id}, flow_id: {flow_id}")
                else:
                    logger.warning(f"无法获取conversation {conversation_id} 的flow_id")
                    return required_file_variables
            except Exception as e:
                logger.error(f"创建对话池失败: {conversation_id} - {e}")
                return required_file_variables
            
        if not conversation_pool:
            # 如果仍然无法获取对话池，说明所有必填文件变量都缺失
            logger.warning(f"无法获取或创建对话池: {conversation_id}")
            return required_file_variables
            
        # 检查每个必填文件变量是否已上传
        for var_name in required_file_variables:
            try:
                actual_var = await conversation_pool.get_variable(var_name)
                if actual_var:
                    # 检查文件是否真正上传
                    if isinstance(actual_var.value, dict):
                        if actual_var.metadata.var_type == VariableType.FILE:
                            # 单个文件：检查file_id是否不为空
                            if not actual_var.value.get("file_id"):
                                missing_variables.append(var_name)
                        elif actual_var.metadata.var_type == VariableType.ARRAY_FILE:
                            # 文件数组：检查file_ids是否非空且有内容
                            file_ids = actual_var.value.get("file_ids", [])
                            if not file_ids or len(file_ids) == 0:
                                missing_variables.append(var_name)
                    else:
                        # 值不是字典格式，说明文件未上传
                        missing_variables.append(var_name)
                else:
                    # 变量不存在，说明文件未上传
                    missing_variables.append(var_name)
            except Exception as e:
                logger.warning(f"检查必填文件变量 {var_name} 时出错: {e}")
                # 出错时也认为是缺失的
                missing_variables.append(var_name)
        
        logger.info(f"缺失的必填文件变量: {missing_variables}")
        return missing_variables
        
    except Exception as e:
        logger.error(f"检查必填文件变量失败: {e}")
        # 出错时返回空列表，允许继续执行
        return []


async def init_task(post_body: RequestData, user_sub: str, session_id: str) -> Task:
    """初始化Task"""
    # 生成group_id
    if not post_body.group_id:
        post_body.group_id = str(uuid.uuid4())
    if post_body.new_task:
        # 创建或还原Task
        task = await TaskManager.get_task(session_id=session_id, post_body=post_body, user_sub=user_sub)
        if task:
            await TaskManager.delete_task_by_task_id(task.id)
    task = await TaskManager.get_task(session_id=session_id, post_body=post_body, user_sub=user_sub)
    # 更改信息并刷新数据库
    if post_body.new_task:
        task.runtime.question = post_body.question
        task.ids.group_id = post_body.group_id
    return task


async def chat_generator(post_body: RequestData, user_sub: str, session_id: str) -> AsyncGenerator[str, None]:
    """进行实际问答，并从MQ中获取消息"""
    try:
        await Activity.set_active(user_sub)

        # 敏感词检查
        if await WordsCheck().check(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            logger.info("[Chat] 问题包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        task = await init_task(post_body, user_sub, session_id)
        
        # 检查必填文件变量
        flow_id_for_check = None
        if post_body.app:
            if post_body.app.flow_id:
                # 如果提供了flow_id，直接使用
                flow_id_for_check = post_body.app.flow_id
            elif post_body.app.app_id:
                # 如果没有flow_id但有app_id，获取默认flow_id
                logger.info(f"[Chat] flow_id为空，尝试通过app_id获取默认flow_id: {post_body.app.app_id}")
                flow_id_for_check = await AppCenterManager.get_default_flow_id(post_body.app.app_id)
                if flow_id_for_check:
                    logger.info(f"[Chat] 获取到默认flow_id: {flow_id_for_check}")
                else:
                    logger.warning(f"[Chat] 无法获取app {post_body.app.app_id} 的默认flow_id")
        
        if flow_id_for_check:
            logger.info(f"[Chat] 开始检查必填文件变量 - flow_id: {flow_id_for_check}, conversation_id: {task.ids.conversation_id}")
            missing_required_files = await check_required_file_variables(
                flow_id_for_check, 
                task.ids.conversation_id, 
                user_sub
            )
            logger.info(f"[Chat] 必填文件检查结果 - 缺失变量: {missing_required_files}")
            if missing_required_files:
                error_msg = f"必填文件变量未上传: {', '.join(missing_required_files)}"
                yield f"data: [ERROR] {error_msg}\n\n"
                logger.error(f"[Chat] {error_msg}")
                await Activity.remove_active(user_sub)
                return
        else:
            logger.info(f"[Chat] 跳过必填文件检查 - 无有效的flow_id。app: {post_body.app}")

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init()

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        scheduler = Scheduler(task, queue, post_body)
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
        # 🔑 修复：对于工作流调试模式或纯逻辑节点，允许答案为空
        is_flow_debug = post_body.app and post_body.app.flow_id
        if not task.runtime.answer and not is_flow_debug:
            logger.error("[Chat] 答案为空且非工作流调试模式")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_sub)
            return
        elif not task.runtime.answer and is_flow_debug:
            logger.info("[Chat] 工作流调试模式，答案为空是正常的（可能是纯逻辑节点）")
            # 为工作流调试提供默认响应
            task.runtime.answer = "工作流执行完成"

        # 对结果进行敏感词检查
        if await WordsCheck().check(task.runtime.answer) != 1:
            yield "data: [SENSITIVE]\n\n"
            logger.info("[Chat] 答案包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 创建新Record，存入数据库
        await save_data(task, user_sub, post_body)

        if post_body.app and post_body.app.flow_id:
            await FlowManager.update_flow_debug_by_app_and_flow_id(
                post_body.app.app_id,
                post_body.app.flow_id,
                debug=True,
            )

        yield "data: [DONE]\n\n"

    except Exception:
        logger.exception("[Chat] 生成答案失败")
        yield "data: [ERROR]\n\n"

    finally:
        await Activity.remove_active(user_sub)


@router.post("/chat")
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

    res = chat_generator(post_body, user_sub, session_id)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop", response_model=ResponseData)
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
