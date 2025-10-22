# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""LLM配置"""

from pydantic import BaseModel, Field

from .embedding import Embedding
from .llm import LLM


class LLMConfig(BaseModel):
    """LLM配置"""

    reasoning: LLM = Field(description="推理LLM")
    function: LLM | None = Field(description="函数LLM")
    embedding: Embedding | None = Field(description="Embedding")

    class Config:
        """配置"""

        arbitrary_types_allowed = True
