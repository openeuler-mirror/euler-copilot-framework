# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import re
from typing import List, Dict, Any

from openai import AsyncOpenAI
from sglang import RuntimeEndpoint
from sglang.lang.chat_template import get_chat_template
from sparkai.llm.llm import ChatSparkLLM
from langchain_openai import ChatOpenAI
from langchain_core.messages import ChatMessage as LangchainChatMessage
from sparkai.messages import ChatMessage as SparkChatMessage
import openai
from untruncate_json import untrunc
from json_minify import json_minify

from apps.common.config import config


def get_scheduler() -> RuntimeEndpoint | AsyncOpenAI:
    if config["SCHEDULER_BACKEND"] == "sglang":
        endpoint = RuntimeEndpoint(config["SCHEDULER_URL"], api_key=config["SCHEDULER_API_KEY"])
        endpoint.chat_template = get_chat_template("chatml")
        return endpoint
    else:
        # 使用vllm框架原生的扩展API，支持sm75以下NVIDIA显卡
        client = openai.AsyncOpenAI(
            base_url=config["SCHEDULER_URL"],
            api_key=config["SCHEDULER_API_KEY"],
        )
        return client


async def create_vllm_stream(client: openai.AsyncOpenAI, messages: List[Dict[str, str]],
                              max_tokens: int, extra_body: Dict[str, Any]):
    return client.chat.completions.create(
        model=config["SCHEDULER_MODEL"],
        messages=messages,
        max_tokens=max_tokens,
        extra_body=extra_body,
        top_p=0.5,
        temperature=0.01,
        stream=True
    )

async def stream_to_str(stream) -> str:
    """
    使用拼接的方式将openai client的stream转化为完整结果
    :param stream: openai async迭代器
    :return: 完整的大模型输出
    """
    result = ""
    async for chunk in stream:
        result += chunk.choices[0].delta.content or ""
    return result


def get_llm():
    """
    获取大模型API Client
    :return: OpenAI大模型Client，或星火大模型SDK Client
    """
    if config["MODEL"] == "openai":
        return ChatOpenAI(
            openai_api_key=config["LLM_KEY"],
            openai_api_base=config["LLM_URL"],
            model_name=config["LLM_MODEL"],
            tiktoken_model_name="cl100k_base",
            max_tokens=4096,
            streaming=True,
            temperature=0.07
        )
    elif config["MODEL"] == "spark":
        return ChatSparkLLM(
            spark_app_id=config["SPARK_APP_ID"],
            spark_api_key=config["SPARK_API_KEY"],
            spark_api_secret=config["SPARK_API_SECRET"],
            spark_api_url=config["SPARK_API_URL"],
            spark_llm_domain=config["SPARK_LLM_DOMAIN"],
            request_timeout=600,
            max_tokens=4096,
            streaming=True,
            temperature=0.07
        )
    else:
        raise NotImplementedError


def get_message_model(llm):
    """
    根据大模型Client的Class，获取大模型消息的Class
    :param llm: 大模型Client
    :return: 大模型消息的Class
    """
    if isinstance(llm, ChatOpenAI):
        return LangchainChatMessage
    elif isinstance(llm, ChatSparkLLM):
        return SparkChatMessage
    else:
        raise NotImplementedError


def get_json_code_block(text):
    """
    从大模型的返回信息中提取出JSON代码段
    :param text: 大模型的返回信息
    :return: 提取出的JSON代码段
    """
    pattern = r'```(json)?(.*)```'
    matches = re.search(pattern, text, re.DOTALL)
    raw_result = matches.group(2)
    raw_mini = json_minify(raw_result)
    raw_fixed = untrunc.complete(raw_mini)

    return raw_fixed
