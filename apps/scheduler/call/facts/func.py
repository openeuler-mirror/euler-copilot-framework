# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""记忆提取工具的提示词"""

from typing import Any

from apps.models import LanguageType

DOMAIN_FUNCTION: dict[LanguageType, dict[str, Any]] = {
    LanguageType.CHINESE: {
        "name": "extract_domain",
        "description": "从对话中提取领域关键词标签",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关键词或标签列表",
                },
            },
            "required": ["keywords"],
        },
        "examples": [
            {"keywords": ["北京", "天气"]},
            {"keywords": ["Python", "装饰器", "设计模式"]},
        ],
    },
    LanguageType.ENGLISH: {
        "name": "extract_domain",
        "description": "Extract domain keyword tags from conversation",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords or tags",
                },
            },
            "required": ["keywords"],
        },
        "examples": [
            {"keywords": ["Beijing", "weather"]},
            {"keywords": ["Python", "decorator", "design pattern"]},
        ],
    },
}

FACTS_FUNCTION: dict[LanguageType, dict[str, Any]] = {
    LanguageType.CHINESE: {
        "name": "extract_facts",
        "description": "从对话中提取关键事实信息",
        "parameters": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "从对话中提取的事实条目",
                },
            },
            "required": ["facts"],
        },
        "examples": [
            {"facts": ["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]},
            {"facts": ["用户喜欢看科幻电影", "用户可能对《星际穿越》感兴趣"]},
        ],
    },
    LanguageType.ENGLISH: {
        "name": "extract_facts",
        "description": "Extract key fact information from conversation",
        "parameters": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fact entries extracted from conversation",
                },
            },
            "required": ["facts"],
        },
        "examples": [
            {
                "facts": [
                    "Hangzhou West Lake has Su Causeway, Bai Causeway, Broken Bridge, "
                    "Three Pools Mirroring the Moon, etc.",
                ],
            },
            {"facts": ["User likes watching sci-fi movies", "User may be interested in Interstellar"]},
        ],
    },
}
