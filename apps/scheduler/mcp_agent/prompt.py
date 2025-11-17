# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

GET_FLOW_NAME_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "get_flow_name",
        "description": "根据用户目标生成当前工作流程的描述性名称",
        "parameters": {
            "type": "object",
            "properties": {
                "flow_name": {
                    "type": "string",
                    "description": "MCP 流程名称",
                    "default": "",
                },
            },
            "required": ["flow_name"],
        },
    },
    LanguageType.ENGLISH: {
        "name": "get_flow_name",
        "description": "Generate a descriptive name for the current workflow based on the user's goal",
        "parameters": {
            "type": "object",
            "properties": {
                "flow_name": {
                    "type": "string",
                    "description": "MCP workflow name",
                    "default": "",
                },
            },
            "required": ["flow_name"],
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

# 获取缺失的参数的json结构体
GET_MISSING_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            根据工具执行报错,识别缺失或错误的参数,并将其设置为null,保留正确参数的值。
            **请调用 `get_missing_parameters` 工具返回结果**。

            ## 任务要求
            - **分析报错信息**:定位哪些参数导致了错误
            - **标记问题参数**:将缺失或错误的参数值设为`null`
            - **保留有效值**:未出错的参数保持原值
            - **调用工具返回**:必须调用`get_missing_parameters`工具,将参数JSON作为工具入参返回

            ## 示例

            **工具**: `mysql_analyzer` - 分析MySQL数据库性能

            **当前入参**:
            ```json
            {"host": "192.0.0.1", "port": 3306, "username": "root", "password": "password"}
            ```

            **参数Schema**:
            ```json
            {
              "properties": {
                "host": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "主机地址"},
                "port": {"anyOf": [{"type": "integer"}, {"type": "null"}], "description": "端口号"},
                "username": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "用户名"},
                "password": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "密码"}
              },
              "required": ["host", "port", "username", "password"]
            }
            ```

            **运行报错**: `password is not correct`

            **应调用工具**:
            ```
            get_missing_parameters({"host": "192.0.0.1", "port": 3306, "username": null, "password": null})
            ```

            > 分析:报错提示密码错误,因此将`password`设为`null`;同时将`username`也设为`null`以便用户重新提供凭证

            ---

            ## 当前任务

            **工具**: `{{tool_name}}` - {{tool_description}}

            **当前入参**:
            ```json
            {{input_param}}
            ```

            **参数Schema**:
            ```json
            {{input_schema}}
            ```

            **运行报错**: {{error_message}}

            **请调用 `get_missing_parameters` 工具返回分析结果**。
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Based on tool execution errors, identify missing or incorrect parameters, set them to null, and retain \
correct parameter values.
            **Please call the `get_missing_parameters` tool to return the result**.

            ## Task Requirements
            - **Analyze error messages**: Identify which parameters caused the error
            - **Mark problematic parameters**: Set missing or incorrect parameter values to `null`
            - **Retain valid values**: Keep original values for parameters that didn't cause errors
            - **Call tool to return**: Must call the `get_missing_parameters` tool with the parameter JSON as input

            ## Example

            **Tool**: `mysql_analyzer` - Analyze MySQL database performance

            **Current Input**:
            ```json
            {"host": "192.0.0.1", "port": 3306, "username": "root", "password": "password"}
            ```

            **Parameter Schema**:
            ```json
            {
              "properties": {
                "host": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Host address"},
                "port": {"anyOf": [{"type": "integer"}, {"type": "null"}], "description": "Port number"},
                "username": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Username"},
                "password": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Password"}
              },
              "required": ["host", "port", "username", "password"]
            }
            ```

            **Error**: `password is not correct`

            **Should call tool**:
            ```
            get_missing_parameters({"host": "192.0.0.1", "port": 3306, "username": null, "password": null})
            ```

            > Analysis: Error indicates incorrect password, so set `password` to `null`; also set `username` to `null` \
for user to provide credentials again

            ---

            ## Current Task

            **Tool**: `{{tool_name}}` - {{tool_description}}

            **Current Input**:
            ```json
            {{input_param}}
            ```

            **Parameter Schema**:
            ```json
            {{input_schema}}
            ```

            **Error**: {{error_message}}

            **Please call the `get_missing_parameters` tool to return the analysis result**.
        """,
    ),
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
