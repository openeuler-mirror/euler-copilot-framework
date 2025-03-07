"""常量数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

import logging
from textwrap import dedent

# 新对话默认标题
NEW_CHAT = "New Chat"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 60
# 滑动窗口限流 最大请求数
SLIDE_WINDOW_QUESTION_COUNT = 10
# API Call 最大返回值长度（字符）
MAX_API_RESPONSE_LENGTH = 8192
# Executor最大步骤历史数
STEP_HISTORY_SIZE = 3
# 语义接口目录中工具子目录
CALL_DIR = "call"
# 语义接口目录中服务子目录
SERVICE_DIR = "service"
# 语义接口目录中应用子目录
APP_DIR = "app"
# 语义接口目录中工作流子目录
FLOW_DIR = "flow"
# Scheduler进程数
SCHEDULER_REPLICAS = 2
# 日志记录器
LOGGER = logging.getLogger("ray")

REASONING_BEGIN_TOKEN = [
    "<think>",
]
REASONING_END_TOKEN = [
    "</think>",
]
LLM_CONTEXT_PROMPT = dedent(
    r"""
        以下是对用户和AI间对话的简短总结：
        {{ summary }}

        你作为AI，在回答用户的问题前，需要获取必要信息。为此，你调用了以下工具，并获得了输出：
        <tool_data>
            {% for tool in history_data %}
                <name>{{ tool.step_id }}</name>
                <output>{{ tool.output_data }}</output>
            {% endfor %}
        </tool_data>
    """,
    ).strip("\n")
LLM_DEFAULT_PROMPT = dedent(
    r"""
        <instructions>
            你是一个乐于助人的智能助手。请结合给出的背景信息, 回答用户的提问。
            当前时间：{{ time }}，可以作为时间参照。
            用户的问题将在<user_question>中给出，上下文背景信息将在<context>中给出。
            注意：输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
        </instructions>

        <user_question>
            {{ question }}
        </user_question>

        <context>
            {{ context }}
        </context>
    """,
    ).strip("\n")
RAG_ANSWER_PROMPT = dedent(
    r"""
        <instructions>
            你是由openEuler社区构建的大型语言AI助手。请根据背景信息（包含对话上下文和文档片段），回答用户问题。
            用户的问题将在<user_question>中给出，上下文背景信息将在<context>中给出，文档片段将在<document>中给出。

            注意事项：
            1. 输出不要包含任何XML标签。请确保输出内容的正确性，不要编造任何信息。
            2. 如果用户询问你关于你自己的问题，请统一回答：“我叫EulerCopilot，是openEuler社区的智能助手”。
            3. 背景信息仅供参考，若背景信息与用户问题无关，请忽略背景信息直接作答。
            4. 请在回答中使用Markdown格式，并**不要**将内容放在"```"中。
        </instructions>

        <user_question>
            {{ question }}
        </user_question>

        <context>
            {{ context }}
        </context>

        <document>
            {{ document }}
        </document>

        现在，请根据上述信息，回答用户的问题：
    """,
    ).strip("\n")
