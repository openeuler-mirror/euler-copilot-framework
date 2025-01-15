"""LLM大模型Prompt模板

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.domain import Domain
from apps.llm.patterns.executor import (
    ExecutorBackground,
    ExecutorResult,
    ExecutorThought,
)
from apps.llm.patterns.json import Json
from apps.llm.patterns.recommend import Recommend
from apps.llm.patterns.select import Select

__all__ = [
    "CorePattern",
    "Domain",
    "ExecutorBackground",
    "ExecutorResult",
    "ExecutorThought",
    "Json",
    "Recommend",
    "Select",
]
