# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型服务平台 基类"""

import logging
from abc import abstractmethod
from collections.abc import AsyncGenerator

from apps.constants import LLM_TIMEOUT
from apps.models import LLMData
from apps.schemas.llm import LLMChunk, LLMFunctions

_logger = logging.getLogger(__name__)

class BaseProvider:
    """大模型服务平台 基类"""

    @staticmethod
    def _validate_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """验证消息格式是否正确"""
        if messages[0]["role"] != "system":
            # 添加默认系统消息
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

        if messages[-1]["role"] not in ["user", "tool"]:
            err = f"消息格式错误，最后一个消息必须是用户消息或工具消息：{messages[-1]}"
            raise ValueError(err)

        return messages


    def __init__(self, llm_config: LLMData) -> None:
        """保存LLMConfig"""
        self.config: LLMData = llm_config
        self._timeout: float = LLM_TIMEOUT
        self.full_thinking: str = ""
        self.full_answer: str = ""
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self._check_type()
        self._init_client()

    @abstractmethod
    def _check_type(self) -> None:
        """检查大模型的类型"""
        raise NotImplementedError

    @abstractmethod
    def _init_client(self) -> None:
        """初始化模型API客户端"""

    async def chat(
        self, messages: list[dict[str, str]],
        tools: list[LLMFunctions] | None = None,
        *, include_thinking: bool = False,
        streaming: bool = True,
        temperature: float = 0.7,
    ) -> AsyncGenerator[LLMChunk, None]:
        """聊天"""
        yield LLMChunk(content="")


    async def embedding(self, text: list[str]) -> list[list[float]]:
        """向量化"""
        raise NotImplementedError


