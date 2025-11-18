# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

FINAL_ANSWER: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            综合理解计划执行结果和背景信息，向用户报告目标的完成情况。

            # 用户目标
            {{ goal }}

            # 计划执行情况
            为了完成上述目标，你实施了以下计划：

            {{ memory }}

            # 其他背景信息：
            {{ status }}

            # 现在，请根据以上信息，向用户报告目标的完成情况：
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Based on the understanding of the plan execution results and background information, report to the user \
the completion status of the goal.

            # User goal
            {{ goal }}

            # Plan execution status
            To achieve the above goal, you implemented the following plan:

            {{ memory }}

            # Other background information:
            {{ status }}

            # Now, based on the above information, please report to the user the completion status of the goal:
        """,
    ),
}
MEMORY_TEMPLATE: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            {% if msg_type == "user" %}
            第{{ step_index }}步：{{ step_goal }}
            调用工具 `{{ step_name }}`，并提供参数 `{{ input_data | tojson }}`。
            {% elif msg_type == "assistant" %}
            第{{ step_index }}步执行完成。
            执行状态：{{ step_status }}
            得到数据：`{{ output_data | tojson }}`
            {% endif %}
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            {% if msg_type == "user" %}
            Step {{ step_index }}: {{ step_goal }}
            Called tool `{{ step_name }}` and provided parameters `{{ input_data | tojson }}`
            {% elif msg_type == "assistant" %}
            Step {{ step_index }} execution completed.
            Execution status: {{ step_status }}
            Got data: `{{ output_data | tojson }}`
            {% endif %}
        """,
    ),
}

SELECT_MCP_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "select_mcp",
        "description": "根据推理结果选择最合适的MCP服务器",
        "parameters": {
            "type": "object",
            "properties": {
                "mcp_id": {
                    "type": "string",
                    "description": "MCP Server的ID",
                },
            },
            "required": ["mcp_id"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "select_mcp",
        "description": "Select the most appropriate MCP server based on the reasoning result",
        "parameters": {
            "type": "object",
            "properties": {
                "mcp_id": {
                    "type": "string",
                    "description": "The ID of the MCP Server",
                },
            },
            "required": ["mcp_id"],
        },
    },
}

CREATE_MCP_PLAN_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "create_mcp_plan",
        "description": "生成结构化的MCP计划以实现用户目标。每个步骤应包含步骤ID、内容描述、工具名称和指令。",
        "parameters": {
            "type": "object",
            "properties": {
                "plans": {
                    "type": "array",
                    "description": (
                        "按顺序执行的计划步骤列表。每个步骤使用一个工具，"
                        "并描述要做什么、使用哪个工具以及具体指令。"
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "该步骤的描述。可以使用 Result[i] 语法引用之前的结果。应少于150字。",
                            },
                            "tool": {
                                "type": "string",
                                "description": (
                                    "该步骤使用的工具ID。必须从提供的工具列表中选择。"
                                    "最后一步必须使用 'Final' 工具。"
                                ),
                            },
                            "instruction": {
                                "type": "string",
                                "description": "工具的具体指令。描述该工具在此步骤中应执行的操作。",
                            },
                        },
                        "required": ["content", "tool", "instruction"],
                    },
                    "minItems": 1,
                    "maxItems": 10,
                },
            },
            "required": ["plans"],
            "additionalProperties": False,
        },
    },
    LanguageType.ENGLISH: {
        "name": "create_mcp_plan",
        "description": (
            "Generate a structured MCP plan to achieve the user's goal. "
            "Each step should include a step ID, content description, tool name, and instruction."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plans": {
                    "type": "array",
                    "description": (
                        "List of plan steps to execute sequentially. Each step uses one tool and "
                        "describes what to do, which tool to use, and specific instructions."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": (
                                    "Description of this step. Can reference previous results using "
                                    "Result[i] syntax. Should be under 150 words."
                                ),
                            },
                            "tool": {
                                "type": "string",
                                "description": (
                                    "Tool ID to use for this step. Must be selected from the provided "
                                    "tool list. The final step must use 'Final' tool."
                                ),
                            },
                            "instruction": {
                                "type": "string",
                                "description": (
                                    "Specific instruction for the tool. Describes what the tool should do in this step."
                                ),
                            },
                        },
                        "required": ["content", "tool", "instruction"],
                    },
                    "minItems": 1,
                    "maxItems": 10,
                },
            },
            "required": ["plans"],
            "additionalProperties": False,
        },
    },
}
