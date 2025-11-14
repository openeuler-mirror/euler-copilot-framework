# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的提示词和Function Schema"""

from apps.models import LanguageType

SUGGEST_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "generate_suggestions",
        "description": "基于对话上下文和用户兴趣生成推荐的后续问题",
        "parameters": {
            "type": "object",
            "properties": {
                "predicted_questions": {
                    "type": "array",
                    "description": "预测的问题列表,每个问题应该是完整的疑问句或祈使句",
                    "items": {
                        "type": "string",
                        "description": "单个推荐问题,长度不超过30字",
                    },
                },
            },
            "required": ["predicted_questions"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "generate_suggestions",
        "description": "Generate recommended follow-up questions based on conversation context and user interests",
        "parameters": {
            "type": "object",
            "properties": {
                "predicted_questions": {
                    "type": "array",
                    "description": "List of predicted questions, each should be a complete interrogative or "
                    "imperative sentence",
                    "items": {
                        "type": "string",
                        "description": "Single recommended question, not exceeding 30 words",
                    },
                },
            },
            "required": ["predicted_questions"],
        },
    },
}
