# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""记忆提取工具的提示词"""

from textwrap import dedent
from typing import Any

from apps.models import LanguageType

DOMAIN_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            # 任务说明
            根据对话历史，从下面的"备选提示词列表"中选择最合适的标签。这些标签将用于内容推荐、用户画像构建和个性化服务。

            ## 备选提示词列表
            {{ available_keywords }}

            ## 选择要求

            1. **精准匹配**：只能从备选提示词列表中选择，不要自创新标签
            2. **话题相关性**：选择与对话主题直接相关的标签
            3. **数量控制**：选择3-8个最相关的标签
            4. **质量标准**：
               - 避免选择重复或高度相似的标签
               - 优先选择具有区分度的标签
               - 按相关性从高到低排序
            5. **输出格式**：返回JSON对象，包含keywords字段，值为字符串数组

            ## 示例

            假设备选提示词列表包含：
            ["北京", "上海", "天气", "气温", "Python", "Java", "装饰器", "设计模式", "餐厅", "美食"]

            **示例1：天气查询**
            - 用户："北京天气如何？"
            - 助手："北京今天晴。"
            - 选择结果：["北京", "天气", "气温"]

            **示例2：如果对话内容与备选列表无关**
            - 用户："今天心情不错"
            - 助手："很高兴听到这个消息。"
            - 选择结果：[]（如果备选列表中没有相关标签，返回空数组）
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            # Task Description
            Based on conversation history, select the most appropriate tags from the "Available Keywords List" below. \
These tags will be used for content recommendation, user profiling, and personalized services.

            ## Available Keywords List
            {available_keywords}

            ## Selection Requirements

            1. **Exact Match**: Only select from the available keywords list, do not create new tags
            2. **Topic Relevance**: Select tags directly related to the conversation topic
            3. **Quantity Control**: Select 3-8 most relevant tags
            4. **Quality Standards**:
               - Avoid selecting duplicate or highly similar tags
               - Prioritize selecting distinctive tags
               - Sort by relevance from high to low
            5. **Output Format**: Return JSON object containing keywords field with string array value

            ## Examples

            Assume the available keywords list contains:
            ["Beijing", "Shanghai", "weather", "temperature", "Python", "Java", "decorator", "design pattern", \
"restaurant", "food"]

            **Example 1: Weather Query**
            - User: "What's the weather like in Beijing?"
            - Assistant: "Beijing is sunny today."
            - Selection result: ["Beijing", "weather", "temperature"]

            **Example 2: If conversation content is unrelated to the available list**
            - User: "I'm feeling good today"
            - Assistant: "Glad to hear that."
            - Selection result: [] (return empty array if no relevant tags in the available list)
        """,
    ),
}

FACTS_PROMPT: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            # 任务说明
            从对话中提取关键信息，并将它们组织成独一无二的、易于理解的事实，包含用户偏好、关系、实体等有用信息。

            ## 关注的信息类型

            1. **实体**：对话中涉及到的实体。例如：姓名、地点、组织、事件等
            2. **偏好**：对待实体的态度。例如喜欢、讨厌等
            3. **关系**：用户与实体之间，或两个实体之间的关系。例如包含、并列、互斥等
            4. **动作**：对实体产生影响的具体动作。例如查询、搜索、浏览、点击等

            ## 提取要求

            1. 事实必须准确，只能从对话中提取
            2. 事实必须清晰、简洁、易于理解，每条事实少于30个字
            3. 输出格式：返回JSON对象，包含facts字段，值为字符串数组

            ## 示例

            **示例1：景点查询**
            - 用户："杭州西湖有哪些景点？"
            - 助手："西湖周围有许多著名的景点，包括苏堤、白堤、断桥、三潭印月等。"
            - 提取结果：["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]

            **示例2：用户偏好**
            - 用户："我喜欢看科幻电影"
            - 助手："科幻电影确实很吸引人，比如《星际穿越》等。"
            - 提取结果：["用户喜欢看科幻电影", "用户可能对《星际穿越》感兴趣"]
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            # Task Description
            Extract key information from the conversation and organize it into unique, easily understandable facts, \
including user preferences, relationships, entities, etc.

            ## Information Types to Focus On

            1. **Entities**: Entities involved in the conversation. For example: names, locations, organizations, \
events, etc.
            2. **Preferences**: Attitudes towards entities. For example: like, dislike, etc.
            3. **Relationships**: Relationships between users and entities, or between two entities. For example: \
include, parallel, mutually exclusive, etc.
            4. **Actions**: Specific actions that affect entities. For example: query, search, browse, click, etc.

            ## Extraction Requirements

            1. Facts must be accurate and can only be extracted from the conversation
            2. Facts must be clear, concise, and easy to understand, each fact less than 30 words
            3. Output format: Return JSON object containing facts field with string array value

            ## Examples

            **Example 1: Attraction Query**
            - User: "What are the attractions in Hangzhou West Lake?"
            - Assistant: "Notable attractions include Su Causeway, Bai Causeway, Broken Bridge, etc."
            - Extraction result: ["Hangzhou West Lake has Su Causeway, Bai Causeway, Broken Bridge, etc."]

            **Example 2: User Preference**
            - User: "I like watching sci-fi movies"
            - Assistant: "Sci-fi movies are indeed attractive, such as Interstellar."
            - Extraction result: ["User likes watching sci-fi movies", "User may be interested in Interstellar"]
        """,
    ),
}

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
