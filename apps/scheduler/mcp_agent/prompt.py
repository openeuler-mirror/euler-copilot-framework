# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from pathlib import Path
from textwrap import dedent

from apps.models import LanguageType


def _load_prompt(prompt_id: str, language: LanguageType) -> str:
    """
    从Markdown文件加载提示词

    :param prompt_id: 提示词ID，例如 "gen_params" 等
    :param language: 语言类型
    :return: 提示词内容
    """
    # 组装Prompt文件路径: prompt_id.language.md (例如: gen_params.en.md)
    filename = f"{prompt_id}.{language.value}.md"
    prompt_dir = Path(__file__).parent.parent.parent / "data" / "prompts" / "system" / "mcp"
    prompt_file = prompt_dir / filename
    return prompt_file.read_text(encoding="utf-8")

GENERATE_FLOW_NAME: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            ## 任务
            根据用户目标生成描述性的工作流程名称。

            ## 要求
            - **简洁明了**：准确表达达成目标的过程，长度控制在20字以内
            - **包含关键操作**：体现核心步骤（如"扫描"、"分析"、"调优"等）
            - **通俗易懂**：避免过于专业的术语

            ## 示例
            **用户目标**：我需要扫描当前mysql数据库，分析性能瓶颈，并调优

            **输出**：扫描MySQL数据库并分析性能瓶颈，进行调优

            ---
            **用户目标**：{{goal}}
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            ## Task
            Generate a descriptive workflow name based on the user's goal.

            ## Requirements
            - **Concise and clear**: Accurately express the process, keep under 20 words
            - **Include key operations**: Reflect core steps (e.g., "scan", "analyze", "optimize")
            - **Easy to understand**: Avoid overly technical terminology

            ## Example
            **User Goal**: I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.

            **Output**: Scan MySQL database, analyze performance bottlenecks, and optimize

            ---
            **User Goal**: {{goal}}
        """,
    ).strip("\n"),
}

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
        "examples": [
            {
                "flow_name": "扫描MySQL数据库并分析性能瓶颈,进行调优",
            },
        ],
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
        "examples": [
            {
                "flow_name": "Scan MySQL database, analyze performance bottlenecks, and optimize",
            },
        ],
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
        "examples": [
            {
                "tool_name": "mcp_tool_1",
                "description": "扫描ip为192.168.1.1的MySQL数据库,端口为3306,用户名为root,密码为password的数据库性能",
            },
        ],
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
        "examples": [
            {
                "tool_name": "mcp_tool_1",
                "description": "Scan MySQL database performance at 192.168.1.1:3306 with user root",
            },
        ],
    },
}

GEN_STEP: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
        你的任务是分析对话历史和用户目标，然后**调用`create_next_step`函数**来规划下一个执行步骤。

        ## 重要提醒
        **你必须且只能调用名为`create_next_step`的函数**，该函数接受两个参数：
        1. `tool_name`: 从下方可用工具列表中选择一个工具名称
        2. `description`: 清晰描述本步骤要完成的具体任务

        ## 可用工具列表
        {% for tool in tools %}
        - **工具名**: `{{tool.toolName}}`
          **功能描述**: {{tool.description}}
        {% endfor %}

        ## 调用规范
        - **函数名固定**: 必须调用`create_next_step`，不要使用工具名作为函数名
        - **tool_name的值**: 必须是上述可用工具列表中的某个工具名称
        - **description的值**: 描述本步骤的具体操作内容
        - **任务完成时**: 如果用户目标已经完成，将`tool_name`参数设为`Final`

        ## 错误示例❌（严禁模仿）
        ```
        # 错误：直接使用工具名作为函数名或返回工具名的字典
        {'Final': '{"description": "任务完成"}'}
        ```

        ## 正确示例✅
        ```
        # 正确：调用create_next_step函数，tool_name参数的值才是工具名称
        create_next_step(
            tool_name="Final",
            description="已完成所有分析任务，可以结束流程"
        )
        ```

        ---
        ## 当前任务
        **用户目标**: {{goal}}

        请根据上方对话历史中已执行步骤的结果，**调用`create_next_step`函数**规划下一步。
        记住：函数名必须是`create_next_step`，`tool_name`参数的值才是具体的工具名称。
        """,
    ).strip(),
    LanguageType.ENGLISH: dedent(
        r"""
        Your task is to analyze the conversation history and user goal, then **call the `create_next_step` \
function** to plan the next execution step.

        ## Important Reminder
        **You must and can only call the function named `create_next_step`**, which accepts two parameters:
        1. `tool_name`: Select a tool name from the available tools list below
        2. `description`: Clearly describe the specific task this step will accomplish

        ## Available Tools List
        {% for tool in tools %}
        - **Tool Name**: `{{tool.toolName}}`
          **Description**: {{tool.description}}
        {% endfor %}

        ## Calling Specifications
        - **Fixed function name**: Must call `create_next_step`, do not use tool names as function names
        - **tool_name value**: Must be one of the tool names from the available tools list above
        - **description value**: Describe the specific operations of this step
        - **When task completes**: If the user goal is achieved, set `tool_name` parameter to `Final`

        ## Incorrect Examples ❌ (Strictly Forbidden)
        ```
        # Error: Using tool name as function name or returning a dictionary with tool name as key
        {'Final': '{"description": "Task completed"}'}
        ```

        ## Correct Examples ✅
        ```
        # Correct: Call create_next_step function, the tool_name parameter value is the tool name
        create_next_step(
            tool_name="Final",
            description="All analysis tasks completed, workflow can be ended"
        )
        ```

        ---
        ## Current Task
        **User Goal**: {{goal}}

        Please **call the `create_next_step` function** to plan the next step based on the results of \
executed steps in the conversation history above.
        Remember: The function name must be `create_next_step`, and the `tool_name` parameter value is \
the specific tool name.
        """,
    ).strip(),
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
        "examples": [
            {
                "risk": "medium",
                "reason": (
                    "当前工具将连接到MySQL数据库并分析性能，可能会对数据库性能产生一定影响。"
                    "请确保在非生产环境中执行此操作。"
                ),
            },
        ],
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
        "examples": [
            {
                "risk": "medium",
                "reason": (
                    "This tool will connect to a MySQL database and analyze performance, "
                    "which may impact database performance. This operation should only be "
                    "performed in a non-production environment."
                ),
            },
        ],
    },
}

RISK_EVALUATE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            评估以下工具执行的安全风险等级，并说明风险原因。

            ## 评估要求
            - **风险等级**: 从 `low` (低)、`medium` (中)、`high` (高) 中选择
            - **风险分析**: 说明可能的安全隐患、性能影响或操作风险
            - **建议**: 如有必要，提供安全执行建议

            ### 示例
            假设评估MySQL性能分析工具（`mysql_analyzer`），该工具将连接到生产环境数据库（MySQL 8.0.26）并执行性能分析。
            由于工具会执行查询和统计操作，可能短暂增加数据库负载，因此风险等级为**中等**。建议在业务低峰期执行此操作，避免影响生产服务的正常运行。

            ---

            ## 工具信息
            **名称**: {{tool_name}}
            **描述**: {{tool_description}}

            ## 输入参数
            ```json
            {{input_param}}
            ```

            {% if additional_info %}
            ## 上下文信息
            {{additional_info}}
            {% endif %}
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Evaluate the security risk level for executing the following tool and explain the reasons.

            ## Assessment Requirements
            - **Risk Level**: Choose from `low`, `medium`, or `high`
            - **Risk Analysis**: Explain potential security risks, performance impacts, or operational concerns
            - **Recommendations**: Provide safe execution guidance if necessary

            ### Example
            Consider evaluating a MySQL performance analysis tool (`mysql_analyzer`) that will connect to a production \
database (MySQL 8.0.26) and perform performance analysis.
            Since the tool will execute queries and statistical operations, it may temporarily increase database load, \
resulting in a **medium** risk level. It is recommended to execute this operation during off-peak business hours to \
avoid impacting normal production services.

            ---

            ## Tool Information
            **Name**: {{tool_name}}
            **Description**: {{tool_description}}

            ## Input Parameters
            ```json
            {{input_param}}
            ```

            {% if additional_info %}
            ## Context Information
            {{additional_info}}
            {% endif %}
        """,
    ),
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
        "examples": [
            {
                "is_param_error": True,
            },
        ],
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
        "examples": [
            {
                "is_param_error": True,
            },
        ],
    },
}

IS_PARAM_ERROR: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            判断以下工具执行失败是否由参数错误导致,并调用 check_parameter_error 工具返回结果。

            **判断标准**：
            - **参数错误**：缺失必需参数、参数值不正确、参数格式/类型错误等
            - **非参数错误**：权限问题、网络故障、系统异常、业务逻辑错误等

            **示例**：当mysql_analyzer工具入参为 {"host": "192.0.0.1", ...}，报错"host is not correct"时，
            错误明确指出host参数值不正确，属于**参数错误**,应调用工具返回 {"is_param_error": true}

            ---

            **用户目标**：{{goal}}

            **当前失败步骤**（步骤{{step_id}}）：
            - 工具：{{step_name}}
            - 目标：{{step_goal}}
            - 入参：{{input_params}}
            - 报错：{{error_message}}

            请基于报错信息和上下文综合判断，调用 check_parameter_error 工具返回判断结果。
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Determine whether the following tool execution failure is caused by parameter errors, and call the \
check_parameter_error tool to return the result.

            **Judgment Criteria**:
            - **Parameter errors**: missing required parameters, incorrect parameter values, parameter format/type \
errors, etc.
            - **Non-parameter errors**: permission issues, network failures, system exceptions, business logic \
errors, etc.

            **Example**: When the mysql_analyzer tool has input {"host": "192.0.0.1", ...} and error "host is not \
correct", the error explicitly indicates the host parameter value is incorrect, which is a **parameter error**, \
should call the tool to return {"is_param_error": true}

            ---

            **User Goal**: {{goal}}

            **Current Failed Step** (Step {{step_id}}):
            - Tool: {{step_name}}
            - Goal: {{step_goal}}
            - Input: {{input_params}}
            - Error: {{error_message}}

            Please make a comprehensive judgment based on the error message and context, and call the \
check_parameter_error tool to return the result.
        """,
    ),
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


def get_gen_params_prompt(language: LanguageType) -> str:
    """
    获取GEN_PARAMS提示词

    :param language: 语言类型
    :return: 提示词内容
    """
    return _load_prompt("gen_params", language)


REPAIR_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个工具参数修复器。
            你的任务是根据当前的工具信息、目标、工具入参的schema、工具当前的入参、工具的报错、补充的参数和补充的参数描述，修复当前工具的入参。

            注意：
            1.最终修复的参数要符合目标和工具入参的schema。

            # 样例
            ## 工具信息
            <tool>
                <name>mysql_analyzer</name>
                <description>分析MySQL数据库性能</description>
            </tool>

            ## 总目标
            我需要扫描当前mysql数据库，分析性能瓶颈, 并调优

            ## 当前阶段目标
            我要连接MySQL数据库，分析性能瓶颈，并调优。

            ## 工具入参的schema
            {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "MySQL数据库的主机地址"
                    },
                    "port": {
                        "type": "integer",
                        "description": "MySQL数据库的端口号"
                    },
                    "username": {
                        "type": "string",
                        "description": "MySQL数据库的用户名"
                    },
                    "password": {
                        "type": "string",
                        "description": "MySQL数据库的密码"
                    }
                },
                "required": ["host", "port", "username", "password"]
            }

            ## 工具当前的入参
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## 工具的报错
            执行端口扫描命令时，出现了错误：`password is not correct`。

            ## 补充的参数
            {
                "username": "admin",
                "password": "admin123"
            }

            ## 补充的参数描述
            用户希望使用admin用户和admin123密码来连接MySQL数据库。

            ## 输出
            ```json
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "admin",
                "password": "admin123"
            }
            ```

            # 现在开始修复工具入参：
            ## 工具
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
            </tool>

            ## 总目标
            {{goal}}

            ## 当前阶段目标
            {{current_goal}}

            ## 工具入参Schema
            {{input_schema}}

            ## 工具当前的入参
            {{input_params}}

            ## 运行报错
            {{error_message}}

            ## 补充的参数
            {{params}}

            ## 补充的参数描述
            {{params_description}}

            ## 输出
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a tool parameter fixer.
            Your task is to fix the current tool input parameters based on the current tool information, tool input \
parameter schema, tool current input parameters, tool error, supplemented parameters, and supplemented \
parameter descriptions.

            # Example
            ## Tool information
            <tool>
                <name>mysql_analyzer</name>
                <description>Analyze MySQL database performance</description>
            </tool>

            ## Tool input parameter schema
            {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "MySQL database host address"
                    },
                    "port": {
                        "type": "integer",
                        "description": "MySQL database port number"
                    },
                    "username": {
                        "type": "string",
                        "description": "MySQL database username"
                    },
                    "password": {
                        "type": "string",
                        "description": "MySQL database password"
                    }
                },
                "required": ["host", "port", "username", "password"]
            }

            ## Current tool input parameters
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## Tool error
            When executing the port scan command, an error occurred: `password is not correct`.

            ## Supplementary parameters
            {
                "username": "admin",
                "password": "admin123"
            }

            ## Supplementary parameter description
            The user wants to use the admin user and the admin123 password to connect to the MySQL database.

            ## Output
            ```json
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "admin",
                "password": "admin123"
            }
            ```

            # Now start fixing tool input parameters:
            ## Tool
            <tool>
                <name> {{tool_name}} </name>
                <description> {{tool_description}} </description>
            </tool>

            ## Tool input schema
            {{input_schema}}

            ## Current tool input parameters
            {{input_params}}

            ## Runtime error
            {{error_message}}

            ## Supplementary parameters
            {{params}}

            ## Supplementary parameter descriptions
            {{params_description}}

            ## Output
        """,
    ),
}

GET_MISSING_PARAMS_FUNCTION: dict[LanguageType, dict] = {
    LanguageType.CHINESE: {
        "name": "get_missing_parameters",
        "description": "根据错误反馈提取并提供缺失或错误的参数",
        "parameters": None,
    },
    LanguageType.ENGLISH: {
        "name": "get_missing_parameters",
        "description": "Extract and provide the missing or incorrect parameters based on error feedback",
        "parameters": None,
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
