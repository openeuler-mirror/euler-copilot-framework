# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from apps.models import LanguageType

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

UPDATE_TOOL_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "update_todo_list",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {
                "todo_list": {
                    "type": "string",
                    "description": "更新后的待办列表",
                },
            },
            "required": ["todo_list"],
        },
        "output": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "执行状态",
                },
            },
            "required": ["status"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "update_todo_list",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {
                "todo_list": {
                    "type": "string",
                    "description": "The updated todo list",
                },
            },
            "required": ["todo_list"],
        },
        "output": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Execution status",
                },
            },
            "required": ["status"],
        },
    },
}

READ_TOOL_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "read_todo_list",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "output": {
            "type": "object",
            "properties": {
                "todo": {
                    "type": "string",
                    "description": "当前待办列表内容",
                },
            },
            "required": ["todo"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "read_todo_list",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "output": {
            "type": "object",
            "properties": {
                "todo": {
                    "type": "string",
                    "description": "Current todo list content",
                },
            },
            "required": ["todo"],
        },
    },
}
