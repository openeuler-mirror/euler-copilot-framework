# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

GET_AGENT_NAME_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "generate_agent_name",
        "description": "根据用户目标生成Agent的描述性名称",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Agent 描述性名称",
                    "default": "",
                },
            },
            "required": ["name"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "generate_agent_name",
        "description": "Generate a descriptive name for the Agent based on the user's goal",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Agent descriptive name",
                    "default": "",
                },
            },
            "required": ["name"],
        },
    },
}

CREATE_NEXT_STEP_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "create_next_step",
        "description": "根据当前的目标、计划和历史，选择合适的工具并定义其参数来创建下一个执行步骤",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "工具名称，必须从可用工具列表中选择一个",
                    "enum": [],
                },
                "description": {
                    "type": "string",
                    "description": "步骤描述，清晰说明本步骤要做什么",
                },
            },
            "required": ["tool_name", "description"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "create_next_step",
        "description": (
            "Create the next execution step in the workflow by selecting "
            "an appropriate tool and defining its parameters"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name, must be selected from the available tools list",
                    "enum": [],
                },
                "description": {
                    "type": "string",
                    "description": "Step description, clearly explain what this step will do",
                },
            },
            "required": ["tool_name", "description"],
        },
    },
}

EVALUATE_TOOL_RISK_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "evaluate_tool_risk",
        "description": "评估工具执行的风险等级和安全问题",
        "parameters": {
            "type": "object",
            "properties": {
                "risk": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "风险等级：低(low)、中(medium)、高(high)",
                },
                "reason": {
                    "type": "string",
                    "description": "风险评估的原因说明",
                    "default": "",
                },
            },
            "required": ["risk", "reason"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "evaluate_tool_risk",
        "description": (
            "Evaluate the risk level and safety concerns of executing "
            "a specific tool with given parameters"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "risk": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Risk level: low, medium, or high",
                },
                "reason": {
                    "type": "string",
                    "description": "Explanation of the risk assessment",
                    "default": "",
                },
            },
            "required": ["risk", "reason"],
        },
    },
}

IS_PARAM_ERROR_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "check_parameter_error",
        "description": "判断错误信息是否是参数相关的错误",
        "parameters": {
            "type": "object",
            "properties": {
                "is_param_error": {
                    "type": "boolean",
                    "description": "是否是参数错误",
                    "default": False,
                },
            },
            "required": ["is_param_error"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "check_parameter_error",
        "description": "Determine whether an error message indicates a parameter-related error",
        "parameters": {
            "type": "object",
            "properties": {
                "is_param_error": {
                    "type": "boolean",
                    "description": "Whether it is a parameter error",
                    "default": False,
                },
            },
            "required": ["is_param_error"],
        },
    },
}

GET_MISSING_PARAMS_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "get_missing_parameters",
        "description": "根据工具执行报错，识别缺失或错误的参数，并将其设置为null。保留正确参数的值。",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    LanguageType.ENGLISH: {
        "name": "get_missing_parameters",
        "description": "Identify missing or incorrect parameters based on tool execution errors, set them to null, "
                       "and retain correct parameter values",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

FINAL_ANSWER: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            综合理解计划执行结果和背景信息，向用户报告目标的完成情况。

            # 用户目标
            {{goal}}

            # 现在，请根据以上信息，向用户报告目标的完成情况：

        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Comprehensively understand the plan execution results and background information, and report the goal \
completion status to the user.

            # User Goal
            {{goal}}

            # Now, based on the above information, report the goal completion status to the user:

        """,
    ),
}
