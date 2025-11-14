# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具的提示词"""

from apps.models import LanguageType

QUESTION_REWRITE_FUNCTION: dict[LanguageType, dict[str, object]] = {
    LanguageType.CHINESE: {
        "name": "rewrite_question",
        "description": "基于上下文优化用户问题，使其更适合知识库检索",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "优化后的问题。应该完整、明确、包含关键信息，便于知识库检索",
                },
            },
            "required": ["question"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "rewrite_question",
        "description": "Optimize user question based on context for better knowledge base retrieval",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The optimized question that is complete, clear, and retrieval-friendly",
                },
            },
            "required": ["question"],
        },
    },
}
