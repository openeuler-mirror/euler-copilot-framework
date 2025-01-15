"""推理/生成大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator

import tiktoken
from langchain_core.messages import ChatMessage as LangchainChatMessage
from langchain_openai import ChatOpenAI
from sparkai.llm.llm import ChatSparkLLM
from sparkai.messages import ChatMessage as SparkChatMessage

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.manager.task import TaskManager


class ReasoningLLM(metaclass=Singleton):
    """调用用于推理/生成的大模型"""

    _encoder = tiktoken.get_encoding("cl100k_base")

    def __init__(self) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        if config["MODEL"] == "openai":
            self._client =  ChatOpenAI(
                api_key=config["LLM_KEY"],
                base_url=config["LLM_URL"],
                model=config["LLM_MODEL"],
                tiktoken_model_name="cl100k_base",
                streaming=True,
            )
        elif config["MODEL"] == "spark":
            self._client = ChatSparkLLM(
                spark_app_id=config["SPARK_APP_ID"],
                spark_api_key=config["SPARK_API_KEY"],
                spark_api_secret=config["SPARK_API_SECRET"],
                spark_api_url=config["SPARK_API_URL"],
                spark_llm_domain=config["SPARK_LLM_DOMAIN"],
                request_timeout=600,
                streaming=True,
            )
        else:
            err = "暂不支持此种大模型API"
            raise NotImplementedError(err)


    @staticmethod
    def _construct_openai_message(messages: list[dict[str, str]]) -> list[LangchainChatMessage]:
        """模型类型为OpenAI API时：构造消息列表

        :param messages: 原始的消息，形如`{"role": "xxx", "content": "xxx"}`
        :returns: 构造后的消息内容
        """
        return [LangchainChatMessage(content=msg["content"], role=msg["role"]) for msg in messages]


    @staticmethod
    def _construct_spark_message(messages: list[dict[str, str]]) -> list[SparkChatMessage]:
        """当模型类型为星火（星火SDK时），构造消息

        :param messages: 原始的消息，形如`{"role": "xxx", "content": "xxx"}`
        :return: 构造后的消息内容
        """
        return [SparkChatMessage(content=msg["content"], role=msg["role"]) for msg in messages]


    def _calculate_token_length(self, messages: list[dict[str, str]], *, pure_text: bool = False) -> int:
        """使用ChatGPT的cl100k tokenizer，估算Token消耗量"""
        result = 0
        if not pure_text:
            result += 3 * (len(messages) + 1)

        for msg in messages:
            result += len(self._encoder.encode(msg["content"]))

        return result


    async def call(self, task_id: str, messages: list[dict[str, str]],
                   max_tokens: int = 8192, temperature: float = 0.07, *, streaming: bool = True) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种

        :param task_id: 任务ID
        :param messages: 原始消息
        :param streaming: 是否启用流式输出
        :param max_tokens: 最大Token数
        :param temperature: 模型温度（随机化程度）
        """
        input_tokens = self._calculate_token_length(messages)

        if config["MODEL"] == "openai":
            msg_list = self._construct_openai_message(messages)
        elif config["MODEL"] == "spark":
            msg_list = self._construct_spark_message(messages)
        else:
            err = "暂不支持此种大模型API"
            raise NotImplementedError(err)

        if streaming:
            result = ""
            async for chunk in self._client.astream(msg_list, max_tokens=max_tokens, temperature=temperature):  # type: ignore[arg-type]
                yield str(chunk.content)
                result += str(chunk.content)
        else:
            result = await self._client.ainvoke(msg_list, max_tokens=max_tokens, temperature=temperature)  # type: ignore[arg-type]
            yield str(result.content)
            result = str(result.content)

        output_tokens = self._calculate_token_length([{"role": "assistant", "content": result}], pure_text=True)
        await TaskManager.update_token_summary(task_id, input_tokens, output_tokens)
