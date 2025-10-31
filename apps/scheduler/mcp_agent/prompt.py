# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

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
                "tool_id": {
                    "type": "string",
                    "description": "工具ID",
                    "enum": [],
                },
                "description": {
                    "type": "string",
                    "description": "步骤描述",
                },
            },
            "required": ["tool_id", "description"],
        },
        "examples": [
            {
                "tool_id": "mcp_tool_1",
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
                "tool_id": {
                    "type": "string",
                    "description": "Tool ID",
                    "enum": [],
                },
                "description": {
                    "type": "string",
                    "description": "Step description",
                },
            },
            "required": ["tool_id", "description"],
        },
        "examples": [
            {
                "tool_id": "mcp_tool_1",
                "description": "Scan MySQL database performance at 192.168.1.1:3306 with user root",
            },
        ],
    },
}

GEN_STEP: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            根据用户目标、执行历史和可用工具，生成下一个执行步骤。

            ## 任务要求

            作为计划生成器，你需要：
            - **选择最合适的工具**：从可用工具集中选择当前阶段最适合的工具
            - **推进目标完成**：基于历史记录，制定能完成阶段性任务的步骤
            - **严格使用工具ID**：工具ID必须精确匹配可用工具列表中的ID
            - **判断完成状态**：若目标已达成，选择`Final`工具结束流程

            ## 示例

            假设用户需要扫描一个MySQL数据库（地址192.168.1.1，端口3306，使用root账户和password密码），分析其性能瓶颈并进行调优。
            之前已经完成了端口扫描，确认了3306端口开放。现在需要选择下一步操作。
            查看可用工具列表后，发现有MySQL性能分析工具（mcp_tool_1）、文件存储工具（mcp_tool_2）和结束工具（Final）。
            此时应选择MySQL性能分析工具，并描述这一步要做什么：使用提供的数据库连接信息（192.168.1.1:3306，root/password）来扫描和分析数据库性能。

            ---

            ## 当前任务

            **目标**：{{goal}}

            **历史记录**：
            {{history}}

            **可用工具**：
            {% for tool in tools %}
            - **{{tool.id}}**：{{tool.description}}
            {% endfor %}
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Generate the next execution step based on user goals, execution history, and available tools.

            ## Task Requirements

            As a plan generator, you need to:
            - **Select the most appropriate tool**: Choose the best tool from available tools for the current stage
            - **Advance goal completion**: Based on execution history, formulate steps to complete phased tasks
            - **Strictly use tool IDs**: Tool ID must exactly match the ID in the available tools list
            - **Determine completion status**: If goal is achieved, select `Final` tool to end the workflow

            ## Example

            Suppose the user needs to scan a MySQL database (at 192.168.1.1:3306, using root account with password),
            analyze its performance bottlenecks, and optimize it.
            Previously, a port scan was completed and confirmed that port 3306 is open. Now we need to select the
            next action.
            Looking at the available tools list, there is a MySQL performance analysis tool (mcp_tool_1), a file
            storage tool (mcp_tool_2), and a final tool (Final).
            At this point, we should select the MySQL performance analysis tool and describe what this step will do:
            use the provided database connection information (192.168.1.1:3306, root/password) to scan and analyze
            database performance.

            ---

            ## Current Task

            **Goal**: {{goal}}

            **Execution History**:
            {{history}}

            **Available Tools**:
            {% for tool in tools %}
            - **{{tool.id}}**: {{tool.description}}
            {% endfor %}
        """,
    ),
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
            判断以下工具执行失败是否由参数错误导致，并调用 check_parameter_error 工具返回结果。

            **判断标准**：
            - **参数错误**：缺失必需参数、参数值不正确、参数格式/类型错误等
            - **非参数错误**：权限问题、网络故障、系统异常、业务逻辑错误等

            **示例**：当mysql_analyzer工具入参为 {"host": "192.0.0.1", ...}，报错"host is not correct"时，
            错误明确指出host参数值不正确，属于**参数错误**，应调用工具返回 {"is_param_error": true}

            ---

            **背景信息**：
            - 用户目标：{{goal}}
            - 执行历史：{{history}}

            **当前失败步骤**（步骤{{step_id}}）：
            - 工具：{{step_name}}
            - 说明：{{step_instruction}}
            - 入参：{{input_param}}
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

            **Background**:
            - User goal: {{goal}}
            - Execution history: {{history}}

            **Current Failed Step** (Step {{step_id}}):
            - Tool: {{step_name}}
            - Instruction: {{step_instruction}}
            - Input: {{input_param}}
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

GEN_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            根据总体目标、阶段目标、工具信息和背景信息，生成符合schema的工具参数。

            ## 任务要求
            - **严格遵循Schema**：生成的参数必须完全符合工具入参schema的类型和格式规范
            - **充分理解上下文**：全面分析总体目标、阶段目标和背景信息，提取所有可用的参数值
            - **匹配阶段目标**：确保生成的参数能够完成当前阶段目标

            ## 示例

            **工具**：
            - **名称**：`mysql_analyzer`
            - **描述**：分析MySQL数据库性能

            **总体目标**：扫描MySQL数据库（IP: 192.168.1.1，端口: 3306，用户名: root，密码: password），\
分析性能瓶颈并调优

            **阶段目标**：连接MySQL数据库并分析性能

            **参数Schema**：
            ```json
            {
              "type": "object",
              "properties": {
                "host": {"type": "string", "description": "主机地址"},
                "port": {"type": "integer", "description": "端口号"},
                "username": {"type": "string", "description": "用户名"},
                "password": {"type": "string", "description": "密码"}
              },
              "required": ["host", "port", "username", "password"]
            }
            ```

            **背景信息**：
            - **步骤1**：生成端口扫描命令 → 成功，输出：`{"command": "nmap -sS -p --open 192.168.1.1"}`
            - **步骤2**：执行端口扫描 → 成功，确认3306端口开放

            **输出**：
            ```json
            {
              "host": "192.168.1.1",
              "port": 3306,
              "username": "root",
              "password": "password"
            }
            ```

            ---

            ## 当前任务

            **工具**：
            - **名称**：`{{tool_name}}`
            - **描述**：{{tool_description}}

            **总体目标**：
            {{goal}}

            **阶段目标**：
            {{current_goal}}

            **参数Schema**：
            ```json
            {{input_schema}}
            ```

            **背景信息**：
            {{background_info}}

            **输出**：
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            Generate tool parameters that conform to the schema based on the overall goal, phase goal, tool \
information, and background context.

            ## Task Requirements
            - **Strictly Follow Schema**: Generated parameters must fully conform to the tool input schema's type and \
format specifications
            - **Fully Understand Context**: Comprehensively analyze the overall goal, phase goal, and background \
information to extract all available parameter values
            - **Match Phase Goal**: Ensure the generated parameters can accomplish the current phase goal

            ## Example

            **Tool**:
            - **Name**: `mysql_analyzer`
            - **Description**: Analyze MySQL database performance

            **Overall Goal**: Scan MySQL database (IP: 192.168.1.1, Port: 3306, Username: root, Password: password), \
analyze performance bottlenecks, and optimize

            **Phase Goal**: Connect to MySQL database and analyze performance

            **Parameter Schema**:
            ```json
            {
              "type": "object",
              "properties": {
                "host": {"type": "string", "description": "Host address"},
                "port": {"type": "integer", "description": "Port number"},
                "username": {"type": "string", "description": "Username"},
                "password": {"type": "string", "description": "Password"}
              },
              "required": ["host", "port", "username", "password"]
            }
            ```

            **Background Information**:
            - **Step 1**: Generate port scan command → Success, output: `{"command": "nmap -sS -p --open 192.168.1.1"}`
            - **Step 2**: Execute port scan → Success, confirmed port 3306 is open

            **Output**:
            ```json
            {
              "host": "192.168.1.1",
              "port": 3306,
              "username": "root",
              "password": "password"
            }
            ```

            ---

            ## Current Task

            **Tool**:
            - **Name**: `{{tool_name}}`
            - **Description**: {{tool_description}}

            **Overall Goal**:
            {{goal}}

            **Phase Goal**:
            {{current_goal}}

            **Parameter Schema**:
            ```json
            {{input_schema}}
            ```

            **Background Information**:
            {{background_info}}

            **Output**:
        """,
    ).strip("\n"),
}

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

            # 计划执行情况
            为了完成上述目标，你实施了以下计划：

            {{memory}}

            # 其他背景信息：
            {{status}}

            # 现在，请根据以上信息，向用户报告目标的完成情况：

        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Comprehensively understand the plan execution results and background information, and report the goal \
completion status to the user.

            # User Goal
            {{goal}}

            # Plan Execution Status
            To achieve the above goal, you implemented the following plan:

            {{memory}}

            # Additional Background Information:
            {{status}}

            # Now, based on the above information, report the goal completion status to the user:

        """,
    ),
}
