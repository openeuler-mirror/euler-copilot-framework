# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的提示词和Function Schema"""

from textwrap import dedent

from apps.models import LanguageType

# Function Schema for question suggestion
SUGGEST_FUNCTION_SCHEMA = {
    "name": "generate_suggestions",
    "description": "Generate recommended follow-up questions based on conversation context and user interests / "
    "基于对话上下文和用户兴趣生成推荐的后续问题",
    "parameters": {
        "type": "object",
        "properties": {
            "predicted_questions": {
                "type": "array",
                "description": "List of predicted questions, each should be a complete interrogative or imperative "
                "sentence / 预测的问题列表，每个问题应该是完整的疑问句或祈使句",
                "items": {
                    "type": "string",
                    "description": "Single recommended question, not exceeding 30 words / 单个推荐问题，长度不超过30字",
                },
            },
        },
        "required": ["predicted_questions"],
    },
    "examples": [
        {
            "predicted_questions": [
                "What is the best season to visit Hangzhou? / 杭州的最佳旅游季节是什么时候?",
                "What are the opening hours and ticket information for Lingyin Temple? / "
                "灵隐寺的开放时间和门票信息?",
                "Which attractions in Hangzhou are suitable for family trips? / 杭州有哪些适合亲子游的景点?",
            ],
        },
        {
            "predicted_questions": [
                "What are the characteristics of dictionaries and sets? / 字典和集合有什么特点?",
                "How to handle exceptions in Python? / 如何在Python中处理异常?",
                "How to use list comprehensions? / 列表推导式怎么使用?",
            ],
        },
    ],
}

SUGGEST_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            请根据对话历史和用户兴趣，生成{% if target_num %}{{ target_num }}{% else %}3-5{% endif %}个\
用户可能感兴趣的后续问题。

            {% if history or generated %}
            **已讨论的问题：**
            {% for question in history %}
            - {{ question }}
            {% endfor %}
            {% for question in generated %}
            - {{ question }}
            {% endfor %}
            {% endif %}

            {% if tool %}
            **可用工具：**{{ tool.name }}（{{ tool.description }}）
            {% endif %}

            {% if preference %}
            **用户兴趣：**{{ preference | join('、') }}
            {% endif %}

            **要求：**
            - 以用户口吻提问，使用疑问句或祈使句
            - 每个问题不超过30字，具体明确、富有探索性
            - 避免与已讨论问题重复
            - 问题应与可用工具和用户兴趣相关，能推进对话深度或拓展话题

            **参考示例：**

            示例1 - 旅游场景：
            当用户已讨论"杭州简介、杭州著名景点、西湖门票价格"，可用工具为"景点查询"，
            用户兴趣为"杭州、旅游"时，可生成：
            杭州的最佳旅游季节是什么时候？灵隐寺的开放时间和门票信息？
            杭州有哪些适合亲子游的景点？

            示例2 - 编程场景：
            当用户已讨论"Python基础语法、列表和元组的区别"，可用工具为"代码搜索"，
            用户兴趣为"Python编程、数据结构"时，可生成：
            字典和集合有什么特点？如何在Python中处理异常？列表推导式怎么使用？
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Please generate {% if target_num %}{{ target_num }}{% else %}3-5{% endif %} follow-up questions \
that the user might be interested in, based on conversation history and user interests.

            {% if history or generated %}
            **Questions already discussed:**
            {% for question in history %}
            - {{ question }}
            {% endfor %}
            {% for question in generated %}
            - {{ question }}
            {% endfor %}
            {% endif %}

            {% if tool %}
            **Available tool:** {{ tool.name }} ({{ tool.description }})
            {% endif %}

            {% if preference %}
            **User interests:** {{ preference | join(', ') }}
            {% endif %}

            **Requirements:**
            - Use the user's voice with interrogative or imperative sentences
            - Each question under 30 words, specific and exploratory
            - Avoid repeating discussed questions
            - Questions should relate to available tools and user interests, deepening or expanding the conversation

            **Reference examples:**

            Example 1 - Tourism scenario:
            When the user has discussed "Hangzhou introduction, famous attractions in Hangzhou,
            West Lake ticket prices", available tool is "Scenic Spot Search", and user interests are
            "Hangzhou, Tourism", you can generate:
            What is the best season to visit Hangzhou?
            What are the opening hours and ticket information for Lingyin Temple?
            Which attractions in Hangzhou are suitable for family trips?

            Example 2 - Programming scenario:
            When the user has discussed "Python basics, difference between lists and tuples", available tool is
            "Code Search", and user interests are "Python programming, Data structures", you can generate:
            What are the characteristics of dictionaries and sets? How to handle exceptions in Python?
            How to use list comprehensions?
        """,
    ),
}
