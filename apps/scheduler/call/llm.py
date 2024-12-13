# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 工具：大模型处理

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any
import json

from apps.scheduler.call.core import CoreCall, CallParams
from apps.llm import get_llm, get_message_model
from apps.scheduler.encoder import JSONSerializer

from pydantic import Field
import pytz
from langchain_openai import ChatOpenAI
from sparkai.llm.llm import ChatSparkLLM


class LLMParams(CallParams):
    temperature: float = Field(description="大模型温度设置", default=1.0)
    system_prompt: str = Field(description="大模型系统提示词", default="你是一个乐于助人的助手。")
    user_prompt: str = Field(
        description="大模型用户提示词",
        default=r"""{question}
        
    工具信息：
    {data}
    
    附加信息：
    当前的时间为{time}。{context}
    """)
    timeout: int = Field(description="超时时间", default=30)


class LLM(CoreCall):
    name = "llm"
    description = "大模型调用工具，用于以指定的提示词和上下文信息调用大模型，并获得输出。"

    model: ChatOpenAI | ChatSparkLLM
    params_obj: LLMParams

    def __init__(self, params: Dict[str, Any]):
        self.model = get_llm()
        self.message_class = get_message_model(self.model)

        self.params_obj = LLMParams(**params)

    async def call(self, fixed_params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if fixed_params is not None:
            self.params_obj = LLMParams(**fixed_params)

        # 参数
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        formatter = {
            "time": time,
            "context": self.params_obj.background,
            "question": self.params_obj.question,
            "data": self.params_obj.previous_data,
        }

        timeout = self.params_obj.timeout
        message = [
            self.message_class(role="system", content=self.params_obj.system_prompt.format(**formatter)),
            self.message_class(role="user", content=self.params_obj.user_prompt.format(**formatter)),
        ]

        result = self.model.invoke(message, timeout=timeout)

        return {
            "output": result.content,
            "message": "已成功调用大模型，对之前步骤的输出数据进行了处理",
        }
