# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""记忆提取工具的提示词"""

from textwrap import dedent
from typing import Any

from apps.models import LanguageType

DOMAIN_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            # 任务说明
            根据对话历史，提取推荐系统所需的关键词标签。这些标签将用于内容推荐、用户画像构建和个性化服务。

            ## 提取要求

            1. **关键词类型**：可以是实体名词（人名、地名、组织名）、技术术语、产品名称、时间范围、领域概念等
            2. **话题相关性**：至少提取一个与对话主题直接相关的关键词
            3. **质量标准**：
               - 标签应精准且简洁，每个标签不超过10个字
               - 避免重复或高度相似的标签
               - 优先提取具有区分度的关键词
               - 提取3-8个关键词为宜
            4. **输出格式**：返回JSON对象，包含keywords字段，值为字符串数组

            ## 示例

            **示例1：天气查询**
            - 用户："北京天气如何？"
            - 助手："北京今天晴。"
            - 提取结果：["北京", "天气"]

            **示例2：技术讨论**
            - 用户："介绍一下Python的装饰器"
            - 助手："Python装饰器是一种设计模式。"
            - 提取结果：["Python", "装饰器", "设计模式"]
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            # Task Description
            Extract keyword tags for the recommendation system based on conversation history. These tags will be used \
for content recommendation, user profiling, and personalized services.

            ## Extraction Requirements

            1. **Keyword Types**: Can be entity nouns (names, locations, organizations), technical terms, \
product names, time ranges, domain concepts, etc.
            2. **Topic Relevance**: Extract at least one keyword directly related to the conversation topic
            3. **Quality Standards**:
               - Tags should be precise and concise, each tag not exceeding 10 characters
               - Avoid duplicate or highly similar tags
               - Prioritize extracting distinctive keywords
               - Extract 3-8 keywords as appropriate
            4. **Output Format**: Return JSON object containing keywords field with string array value

            ## Examples

            **Example 1: Weather Query**
            - User: "What's the weather like in Beijing?"
            - Assistant: "Beijing is sunny today."
            - Extraction result: ["Beijing", "weather"]

            **Example 2: Technical Discussion**
            - User: "Tell me about Python decorators"
            - Assistant: "Python decorators are a design pattern."
            - Extraction result: ["Python", "decorator", "design pattern"]
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

DOMAIN_FUNCTION: dict[str, Any] = {
    "name": "extract_domain",
    "description": "从对话中提取领域关键词标签 / Extract domain keyword tags from conversation",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键词或标签列表 / List of keywords or tags",
            },
        },
        "required": ["keywords"],
    },
    "examples": [
        {"keywords": ["北京", "天气"]},
        {"keywords": ["Python", "装饰器", "设计模式"]},
    ],
}

FACTS_FUNCTION: dict[str, Any] = {
    "name": "extract_facts",
    "description": "从对话中提取关键事实信息 / Extract key fact information from conversation",
    "parameters": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "从对话中提取的事实条目 / Fact entries extracted from conversation",
            },
        },
        "required": ["facts"],
    },
    "examples": [
        {"facts": ["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]},
        {"facts": ["用户喜欢看科幻电影", "用户可能对《星际穿越》感兴趣"]},
    ],
}
