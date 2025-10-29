# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具的提示词"""

from textwrap import dedent

from apps.models import LanguageType

QUESTION_REWRITE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
        你需要分析用户的当前提问，结合对话历史上下文，理解用户的真实意图并优化问题表述，使其更适合知识库检索。

        ## 要求
        - 参考对话历史理解用户的真实意图，补全省略的信息（如代词、缩略语等）
        - 如果问题已经足够完整和明确，直接使用原问题，不要过度修改
        - 优化后的问题应该更加精准、具体，便于知识库检索匹配
        - 保持问题的核心语义不变，不要编造原问题中没有的信息
        - 适当扩展相关的关键术语和概念，提高检索召回率

        ## 示例

        **示例1：补全上下文中的指代关系**
        - 对话历史：
          - 用户: openEuler是什么？
          - 助手: openEuler是一个开源操作系统。
        - 当前问题：它的优势有哪些？
        - 优化结果：openEuler操作系统的优势和特点是什么？

        **示例2：扩展关键术语**
        - 对话历史：无
        - 当前问题：如何安装Docker？
        - 优化结果：如何在Linux系统上安装和配置Docker容器引擎？

        ## 用户当前问题
        {{question}}
        """,
    ).strip(),
    LanguageType.ENGLISH: dedent(
        r"""
        Analyze the user's current question in the context of the conversation history to understand their true \
intent and optimize the phrasing for knowledge base retrieval.

        ## Requirements
        - Reference conversation history to understand true intent and complete omitted information (pronouns, \
abbreviations, etc.)
        - If the question is already complete and clear, use it as-is without over-modification
        - The optimized question should be more precise and specific for better knowledge base matching
        - Maintain the core semantics without fabricating information not present in the original question
        - Appropriately expand related key terms and concepts to improve retrieval recall

        ## Examples

        **Example 1: Complete contextual references**
        - Conversation history:
          - User: What is openEuler?
          - Assistant: openEuler is an open source operating system.
        - Current question: What are its features?
        - Optimized result: What are the features and advantages of the openEuler operating system?

        **Example 2: Expand key terms**
        - Conversation history: None
        - Current question: How to install Docker?
        - Optimized result: How to install and configure Docker container engine on Linux system?

        ## User's Current Question
        {{question}}
        """,
    ).strip(),
}

QUESTION_REWRITE_FUNCTION: dict[str, object] = {
    "name": "rewrite_question",
    "description": (
        "基于上下文优化用户问题，使其更适合知识库检索 / "
        "Optimize user question based on context for better knowledge base retrieval"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "优化后的问题。应该完整、明确、包含关键信息，便于知识库检索 / "
                    "The optimized question that is complete, clear, and retrieval-friendly"
                ),
            },
        },
        "required": ["question"],
    },
    "examples": [
        {"question": "openEuler操作系统的优势和特点是什么？"},
        {"question": "How to install and configure Docker container engine on Linux system?"},
    ],
}
