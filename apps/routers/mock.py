"""问答大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import json
import random
import time
import traceback
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from textwrap import dedent
from typing import Annotated, Any, AsyncGenerator, Optional

import aiohttp
import ray
import tiktoken
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.common.config import config
from apps.constants import LOGGER, REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import MockRequestData, RequestData
from apps.entities.scheduler import CallError
from apps.manager.flow import FlowManager
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.scheduler.context import save_data
from apps.service.activity import Activity


class ReasoningLLM:
    """调用用于问答的大模型"""

    _encoder = tiktoken.get_encoding("cl100k_base")

    def __init__(self) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        if not config["LLM_KEY"]:
            self._client = AsyncOpenAI(
                base_url=config["LLM_URL"],
            )
            return

        self._client = AsyncOpenAI(
            api_key=config["LLM_KEY"],
            base_url=config["LLM_URL"],
        )

    def _calculate_token_length(self, messages: list[dict[str, str]], *, pure_text: bool = False) -> int:
        """使用ChatGPT的cl100k tokenizer，估算Token消耗量"""
        result = 0
        if not pure_text:
            result += 3 * (len(messages) + 1)

        for msg in messages:
            result += len(self._encoder.encode(msg["content"]))

        return result

    def _validate_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """验证消息格式是否正确"""
        if messages[0]["role"] != "system":
            # 添加默认系统消息
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

        if messages[-1]["role"] != "user":
            err = f"消息格式错误，最后一个消息必须是用户消息：{messages[-1]}"
            raise ValueError(err)

        return messages

    async def call(
        self,
        messages: list[dict[str, str]],  # noqa: C901
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        *,
        streaming: bool = True,
        result_only: bool = True,
    ) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        # input_tokens = self._calculate_token_length(messages)
        try:
            msg_list = self._validate_messages(messages)
        except ValueError as e:
            err = f"消息格式错误：{e}"
            raise ValueError(err) from e

        if max_tokens is None:
            max_tokens = config["LLM_MAX_TOKENS"]
        if temperature is None:
            temperature = config["LLM_TEMPERATURE"]

        stream = await self._client.chat.completions.create(
            model=config["LLM_MODEL"],
            messages=msg_list,  # type: ignore[]
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )  # type: ignore[]

        reasoning_content = ""
        result = ""

        is_first_chunk = True
        is_reasoning = False
        reasoning_type = ""

        async for chunk in stream:
            # 当前Chunk内的信息
            reason = ""
            text = ""

            if is_first_chunk:
                if hasattr(chunk.choices[0].delta, "reasoning_content"):
                    reason = "<think>" + chunk.choices[0].delta.reasoning_content or ""
                    reasoning_type = "args"
                    is_reasoning = True
                else:
                    for token in REASONING_BEGIN_TOKEN:
                        if token == (chunk.choices[0].delta.content or ""):
                            reason = "<think>"
                            reasoning_type = "tokens"
                            is_reasoning = True
                            break

            # 当前已经不是第一个Chunk了
            is_first_chunk = False

            # 当前是正常问答
            if not is_reasoning:
                text = chunk.choices[0].delta.content or ""

            # 当前处于推理状态
            if not is_first_chunk and is_reasoning:
                # 如果推理内容用特殊参数传递
                if reasoning_type == "args":
                    # 还在推理
                    if hasattr(chunk.choices[0].delta, "reasoning_content"):
                        reason = chunk.choices[0].delta.reasoning_content or ""
                    # 推理结束
                    else:
                        is_reasoning = False
                        reason = "</think>"

                # 如果推理内容用特殊token传递
                elif reasoning_type == "tokens":
                    # 结束推理
                    for token in REASONING_END_TOKEN:
                        if token == (chunk.choices[0].delta.content or ""):
                            is_reasoning = False
                            reason = "</think>"
                            text = ""
                            break
                    # 还在推理
                    if is_reasoning:
                        reason = chunk.choices[0].delta.content or ""

            # 推送消息
            if streaming:
                # 如果需要推送推理内容
                if reason and not result_only:
                    yield reason

                # 推送text
                yield text

            # 整理结果
            reasoning_content += reason
            result += text

        if not streaming:
            if not result_only:
                yield reasoning_content
            yield result

        # LOGGER.info(f"推理LLM：{reasoning_content}\n\n{result}")

        # output_tokens = self._calculate_token_length([{"role": "assistant", "content": result}], pure_text=True)
        # task = ray.get_actor("task")
        # await task.update_token_summary.remote(input_tokens, output_tokens)


class _RAGParams(BaseModel):
    """RAG工具的参数"""

    knowledge_base: str = Field(description="知识库的id", alias="kb_sn")
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    methods: Optional[list[str]] = Field(description="rag检索方法")


class _RAGOutputList(BaseModel):
    """RAG工具的输出"""

    corpus: list[str] = Field(description="知识库的语料列表")


class _RAGOutput(BaseModel):
    """RAG工具的输出"""

    output: _RAGOutputList = Field(description="RAG工具的输出")


router = APIRouter(
    prefix="/api",
    tags=["mock"],
)


async def mock_data(
    post_body: RequestData,
    user_sub: str,
    session_id: str,
):
    try:
        # await Activity.set_active(user_sub)

        # # 生成group_id
        # group_id = str(uuid.uuid4()) if not post_body.group_id else post_body.group_id

        # # 创建或还原Task
        # task_pool = ray.get_actor("task")
        # task = await task_pool.get_task.remote(session_id=session_id, post_body=post_body)
        # task_id = task.record.task_id

        # task.record.group_id = group_id
        # post_body.group_id = group_id
        # await task_pool.set_task.remote(task_id, task)

        _encoder = tiktoken.get_encoding("cl100k_base")

        question = post_body.question
        conversationId = post_body.conversation_id
        appId = post_body.app.app_id if post_body.app else None
        flowId = post_body.app.flow_id if post_body.app else None

        start_message = [
            {  # 任务流开始
                "event": "flow.start",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId": "8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId": flowId,
                    "stepId": "start",
                    "stepStatus": "pending",
                },
                "content": {},
                "metadata": {"inputTokens": 200, "outputTokens": 50, "time_cost": 0.5},
            },
            {
                "event": "init",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId": "8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "content": {
                    "feature": {
                        "enable_feedback": True,
                        "enable_regenerate": True,
                        "max_tokens": 2048,
                        "context_num": 2,
                    },
                },
                "metadata": {"input_tokens": 200, "output_tokens": 50, "time_cost": 0.5},
            },
        ]
        sample_input = {  # 开始节点
            "event": "step.input",
            "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
            "groupId": "8b9d3e6b-a892-4602-b247-35c522d38f13",
            "conversationId": conversationId,
            "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
            "flow": {
                "appId": appId,
                "flowId": flowId,
                "stepId": "start",
                "stepName": "开始",
                "stepStatus": "running",
            },
            "content": {"text": "测试输入"},
            "metadata": {
                "inputTokens": 200,
                "outputTokens": 50,
                "time_cost": 0.5,
            },
        }
        sample_output = {  # 开始节点
            "event": "step.output",
            "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
            "groupId": "8b9d3e6b-a892-4602-b247-35c522d38f13",
            "conversationId": conversationId,
            "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
            "flow": {
                "appId": appId,
                "flowId": flowId,
                "stepId": "start",
                "stepName": "开始",
                "stepStatus": "success",
            },
            "content": {"text": "测试输出"},
            "metadata": {
                "inputTokens": 200,
                "outputTokens": 50,
                "time_cost": 0.5,
            },
        }
        messages = []
        for message in start_message:
            messages.append(message)
        for message in messages:
            if message["event"] == "step.output":
                t = message["metadata"]["time_cost"]
                time.sleep(t)
            elif message["event"] == "text.add":
                t = random.uniform(0.15, 0.2)
                time.sleep(t)
            yield "data: " + json.dumps(message, ensure_ascii=False) + "\n\n"
        mid_message = []

        flow = None
        if appId and flowId:
            flow = await FlowLoader().load(appId, flowId)

        now_flow_item = "start"
        start_time = time.time()
        last_item = ""
        mapp = {}
        params = {}
        params["question"] = question

        if flow is not None:
            LOGGER.info(json.dumps(flow.model_dump_json(exclude_none=True, by_alias=True), ensure_ascii=False))
            for step_id, step in flow.steps.items():
                mapp[step_id] = step.name, step.params
            while now_flow_item != "end":
                if last_item == now_flow_item:
                    break
                # 如果超过10s强制退出
                if time.time() - start_time > 10:
                    break
                last_item = now_flow_item
                for edge in flow.edges:
                    if edge.edge_from.split(".")[0] == now_flow_item:
                        sample_input["flow"]["stepId"] = now_flow_item
                        sample_input["flow"]["stepName"], sample_input["content"] = mapp[now_flow_item]
                        sample_input["content"] = (
                            sample_input["content"]["input_parameters"]
                            if now_flow_item != "start"
                            else sample_input["content"]
                        )
                        if "content" in sample_input and type(sample_input["content"]) == dict:
                            for key, value in sample_input["content"].items():
                                if key in params:
                                    sample_input["content"][key] = params[key]
                                else:
                                    params[key] = value
                        time.sleep(sample_input["metadata"]["time_cost"])
                        yield "data: " + json.dumps(sample_input, ensure_ascii=False) + "\n\n"
                        sample_output["metadata"]["time_cost"] = random.uniform(1.5, 3.5)
                        sample_output["flow"]["stepId"] = now_flow_item
                        sample_output["flow"]["stepName"], sample_output["content"] = mapp[now_flow_item]
                        sample_output["content"] = (
                            sample_output["content"]["output_parameters"]
                            if now_flow_item != "start"
                            else sample_output["content"]
                        )
                        if sample_output["flow"]["stepName"] == "知识库":
                            sample_output["content"] = await call_rag(params)
                        if sample_output["flow"]["stepName"] == "大模型":
                            # sample_output["content"] = await call_llm(params)
                            sample_output["content"] = {"message": "<StreamAnswerResponse>"}
                        if "content" in sample_output and isinstance(sample_output["content"], dict):
                            for key, value in sample_output["content"].items():
                                params[key] = value
                        time.sleep(sample_output["metadata"]["time_cost"])
                        yield "data: " + json.dumps(sample_output, ensure_ascii=False) + "\n\n"
                        now_flow_item = edge.edge_to

        if now_flow_item == "end":
            sample_input["flow"]["stepId"] = now_flow_item
            sample_input["flow"]["stepName"] = "结束"
            yield "data: " + json.dumps(sample_input, ensure_ascii=False) + "\n\n"
            sample_output["flow"]["stepId"] = now_flow_item
            sample_output["flow"]["stepName"] = "结束"
            sample_output["metadata"]["time_cost"] = random.uniform(0.5, 1.5)
            yield "data: " + json.dumps(sample_output, ensure_ascii=False) + "\n\n"

        end_message = [
            {  # flow结束
                "event": "flow.stop",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId": "8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {},
                "content": {},
                "measure": {"inputTokens": 200, "outputTokens": 50, "time_cost": random.uniform(0.5, 1.5)},
            },
        ]
        messages = []
        for message in end_message:
            messages.append(message)
            for message in messages:
                if message["event"] == "step.output":
                    t = message["metadata"]["time_cost"]
                    time.sleep(t)
                elif message["event"] == "text.add":
                    t = random.uniform(0.15, 0.2)
                    time.sleep(t)
                yield "data: " + json.dumps(message, ensure_ascii=False) + "\n\n"

        chat_message = call_llm_stream(params)
        messages = []
        temp_messages = []
        async for message in chat_message:
            yield "data: " + message + "\n\n"
        yield json.dumps(
            {"event": "text.end", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 290},
        )
        if appId and flowId:
            await FlowManager.updata_flow_debug_by_app_and_flow_id(appId, flowId, True)

        # # 获取最终答案
        # task = await task_pool.get_task.remote(task_id)
        # answer_text = task.record.content.answer
        # if not answer_text:
        #     LOGGER.error(msg="Answer is empty")
        #     yield "data: [ERROR]\n\n"
        #     await Activity.remove_active(user_sub)
        #     return

        # # 创建新Record，存入数据库
        # await save_data(task_id, user_sub, post_body, result.used_docs)
    except Exception:
        LOGGER.error(f"Run mock_data failed：{traceback.format_exc()}")
        yield "data: [ERROR]\n\n"


async def call_rag(params: dict = {}):
    url = config["RAG_HOST"].rstrip("/") + "/chunk/get"
    headers = {
        "Content-Type": "application/json",
    }
    params_dict = {
        "kb_sn": params["kb_sn"],
        "top_k": params["top_k"],
        "content": params["question"],
        "retrieval_mode": params["retrieval_mode"],
    }
    # 发送 POST 请求
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params_dict) as response:
            # 检查响应状态码
            if response.status == status.HTTP_200_OK:
                result = await response.json()
                chunk_list = result["data"]
                for i in range(len(chunk_list)):
                    chunk_list[i] = chunk_list[i].replace("\n", "")
                return {"chunk_list": chunk_list}
            text = await response.text()
            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": params["question"],
                    "status": response.status,
                    "text": text,
                },
            )


async def call_llm(params: dict = {}):
    # 构建请求 URL 和 headers
    url = config["LLM_URL"] + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['LLM_KEY']}",  # 添加鉴权 Token
    }
    prompt = params.get("prompt", "")
    chunk_list = params.get("chunk_list", "")
    LOGGER.info("LLM 接收", chunk_list)
    user_call = "请回答问题" + params.get("quetion", "") + "下面是获得的信息："
    # 构建请求体
    payload = {
        "model": params.get("model", config["LLM_MODEL"]),  # 默认模型
        "messages": params.get(
            "messages",
            [{"role": "system", "content": prompt}, {"role": "user", "content": user_call + str(chunk_list)}],
        ),  # 消息列表
        "stream": params.get("stream", False),  # 是否流式返回
        "n": params.get("n", 1),  # 返回的候选答案数量
        "max_tokens": params.get("max_tokens", 4096),  # 最大 token 数量
    }

    # 发送 POST 请求
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            # 检查响应状态码
            if response.status == status.HTTP_200_OK:
                result = await response.json()
                result = result["choices"][0]["message"]["content"]
                LOGGER.info(result)
                result = result.replace("\n\n", "")
                return {"content": result}
            text = await response.text()
            LOGGER.error(f"LLM 调用失败：{text}")
            return None


class _LLMOutput(BaseModel):
    """定义LLM工具调用的输出"""

    message: str = Field(description="大模型输出的文字信息")


async def call_llm_stream(params: dict[str, Any] = {}):
    _encoder = tiktoken.get_encoding("cl100k_base")
    prompt = "你是EulerCopilot，我们向你问了一个问题，需要你完成这个问题，我们会给出对应的信息"
    question = params.get("question", "")
    content = f"问题：{question}\n" + "信息：" + str(params.get("chunk_list", ""))
    message = params.get("messages", [{"role": "system", "content": prompt}, {"role": "user", "content": content}])
    sum = 0
    async for chunk in ReasoningLLM().call(messages=message):
        sum = sum + len(_encoder.encode(chunk))
        chunk = chunk.replace("\n\n", "")
        output = {
            "event": "text.add",
            "content": {"text": chunk},
            "input_tokens": len(_encoder.encode(question)),
            "output_tokens": sum,
        }
        yield json.dumps(output, ensure_ascii=False)


@router.post("/mock/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    post_body: RequestData,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> StreamingResponse:
    """LLM流式对话接口"""
    res = mock_data(
        post_body=post_body,
        user_sub=user_sub,
        session_id=session_id,
    )
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )
