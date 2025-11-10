# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

MCP_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个计划生成器。
            请分析用户的目标，并生成一个计划。你后续将根据这个计划，一步一步地完成用户的目标。

            # 一个好的计划应该：
            1. 能够成功完成用户的目标
            2. 计划中的每一个步骤必须且只能使用一个工具。
            3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
            4. 计划中的最后一步必须是Final工具，以确保计划执行结束。
            5.生成的计划必须要覆盖用户的目标，不能遗漏任何用户目标中的内容。

            # 生成计划时的注意事项：
            - 每一条计划包含3个部分：
                - 计划内容：描述单个计划步骤的大致内容
                - 工具ID：必须从下文的工具列表中选择
                - 工具指令：改写用户的目标，使其更符合工具的输入要求
            - 必须按照如下格式生成计划，不要输出任何额外数据：

            ```json
            {
                "plans": [
                    {
                        "content": "计划内容",
                        "tool": "工具ID",
                        "instruction": "工具指令"
                    }
                ]
            }
            ```

            - 在生成计划之前，请一步一步思考，解析用户的目标，并指导你接下来的生成。\
        思考过程应放置在<thinking></thinking> XML标签中。
            - 计划内容中，可以使用"Result[]"来引用之前计划步骤的结果。例如："Result[3]"表示引用第三条计划执行后的结果。
            - 计划不得多于{{ max_num }}条，且每条计划内容应少于150字。

            # 工具
            你可以访问并使用一些工具，这些工具将在<tools></tools> XML标签中给出。

            <tools>
                {% for tool in tools %}
                - <id>{{ tool.toolName }}</id><description>{{tool.toolName}}；{{ tool.description }}</description>
                {% endfor %}
                - <id>Final</id><description>结束步骤，当执行到这一步时，\
        表示计划执行结束，所得到的结果将作为最终结果。</description>
            </tools>

            # 样例
            ## 目标
            在后台运行一个新的alpine:latest容器，将主机/root文件夹挂载至/data，并执行top命令。

            ## 计划
            <thinking>
            1. 这个目标需要使用Docker来完成,首先需要选择合适的MCP Server
            2. 目标可以拆解为以下几个部分:
               - 运行alpine:latest容器
               - 挂载主机目录
               - 在后台运行
               - 执行top命令
            3. 需要先选择MCP Server,然后生成Docker命令,最后执行命令
            </thinking>

            ```json
            {
                "plans": [
                    {
                        "content": "选择一个支持Docker的MCP Server",
                        "tool": "mcp_selector",
                        "instruction": "需要一个支持Docker容器运行的MCP Server"
                    },
                    {
                        "content": "使用Result[0]中选择的MCP Server，生成Docker命令",
                        "tool": "command_generator",
                        "instruction": "生成Docker命令：在后台运行alpine:latest容器，挂载/root到/data，执行top命令"
                    },
                    {
                        "content": "在Result[0]的MCP Server上执行Result[1]生成的命令",
                        "tool": "command_executor",
                        "instruction": "执行Docker命令"
                    },
                    {
                        "content": "任务执行完成，容器已在后台运行，结果为Result[2]",
                        "tool": "Final",
                        "instruction": ""
                    }
                ]
            }
            ```

            # 现在开始生成计划：
            ## 目标
            {{goal}}

            # 计划
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a helpful intelligent assistant.
            Your task is to select the most appropriate MCP server based on your current goals.

            ## Things to note when selecting an MCP server:
            1. Ensure you fully understand your current goals and select the most appropriate MCP server.
            2. Please select from the provided list of MCP servers; do not generate your own.
            3. Please provide the rationale for your choice before making your selection.
            4. Your current goals will be listed below, along with the list of MCP servers.
               Please include your thought process in the "Thought Process" section and your selection in the \
"Selection Results" section.
            5. Your selection must be in JSON format, strictly following the template below. Do not output any \
additional content:

            ```json
            {
                "mcp": "The name of your selected MCP server"
            }
            ```

            6. The following example is for reference only. Do not use it as a basis for selecting an MCP server.

            ## Example
            ### Goal
            I need an MCP server to complete a task.

            ### MCP Server List
            - **mcp_1**: "MCP Server 1"; Description of MCP Server 1
            - **mcp_2**: "MCP Server 2"; Description of MCP Server 2

            ### Think step by step:
            Because the current goal requires an MCP server to complete a task, select mcp_1.

            ### Select Result
            ```json
            {
                "mcp": "mcp_1"
            }
            ```

            ## Let's get started!
            ### Goal
            {{goal}}

            ### MCP Server List
            {% for mcp in mcp_list %}
            - **{{mcp.id}}**: "{{mcp.name}}"; {{mcp.description}}
            {% endfor %}

            ### Think step by step:
        """,
    ),
}

CREATE_PLAN: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            ## 任务
            分析用户目标并生成执行计划，用于后续逐步完成目标。

            ## 计划要求
            1. **每步一工具**：每个步骤仅使用一个工具
            2. **逻辑清晰**：步骤间有明确依赖关系，无冗余
            3. **目标覆盖**：不遗漏用户目标的任何内容
            4. **步骤上限**：不超过 {{ max_num }} 条，每条不超过150字
            5. **必须结束**：最后一步使用 `Final` 工具

            ## 计划结构
            每条计划包含三要素：
            - **content**：步骤描述，可用 `Result[i]` 引用前序结果
            - **tool**：工具ID（从工具列表中选择）
            - **instruction**：针对工具的具体指令

            ## 工具列表
            {% for tool in tools %}
            - **{{ tool.toolName }}**: {{tool.toolName}}；{{ tool.description }}
            {% endfor %}
            - **Final**: 结束步骤，标志计划执行完成

            ## 示例
            假设用户目标是：在后台运行 alpine:latest 容器，挂载 /root 到 /data，执行 top 命令

            首先分析这个目标：
            - 这需要 Docker 支持，因此第一步应该选择一个支持 Docker 的 MCP Server
            - 接着需要生成符合要求的 Docker 命令，包括容器镜像、目录挂载、后台运行和命令执行
            - 然后执行生成的命令
            - 最后标记任务完成

            基于这个分析，可以生成以下计划：
            - 第一步：选择支持 Docker 的 MCP Server，使用 mcp_selector 工具，\
指令是"需要支持 Docker 容器运行的 MCP Server"
            - 第二步：基于 Result[0] 生成 Docker 命令，使用 command_generator 工具，\
指令是"生成命令：后台运行 alpine:latest，挂载 /root 至 /data，执行 top"
            - 第三步：在 Result[0] 上执行 Result[1] 的命令，使用 command_executor 工具，指令是"执行 Docker 命令"
            - 第四步：容器已运行，输出 Result[2]，使用 Final 工具，指令为空

            ## 用户目标
            {{goal}}

            ## 请生成计划
            先分析目标，理清思路，然后生成结构化的执行计划。
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            ## Task
            Analyze the user's goal and generate an execution plan to accomplish the goal step by step.

            ## Plan Requirements
            1. **One Tool Per Step**: Each step uses only one tool
            2. **Clear Logic**: Steps have explicit dependencies, no redundancy
            3. **Complete Coverage**: Don't miss any part of the user's goal
            4. **Step Limit**: Maximum {{ max_num }} steps, each under 150 words
            5. **Must End**: Final step must use the `Final` tool

            ## Plan Structure
            Each plan contains three elements:
            - **content**: Step description, can reference previous results with `Result[i]`
            - **tool**: Tool ID (selected from tool list)
            - **instruction**: Specific instruction for the tool

            ## Tool List
            {% for tool in tools %}
            - **{{ tool.toolName }}**: {{tool.toolName}}; {{ tool.description }}
            {% endfor %}
            - **Final**: End step, marks plan execution complete

            ## Example
            Suppose the user's goal is: Run alpine:latest container in background, mount /root to /data, \
execute top command

            First, analyze this goal:
            - This requires Docker support, so the first step should select an MCP Server with Docker capability
            - Next, need to generate a Docker command that meets the requirements, including container image, \
directory mount, background execution, and command execution
            - Then execute the generated command
            - Finally, mark the task as complete

            Based on this analysis, the following plan can be generated:
            - Step 1: Select MCP Server with Docker support, using mcp_selector tool, \
instruction is "Need MCP Server supporting Docker container operation"
            - Step 2: Generate Docker command based on Result[0], using command_generator tool, \
instruction is "Generate command: run alpine:latest in background, mount /root to /data, execute top"
            - Step 3: Execute Result[1] command on Result[0], using command_executor tool, \
instruction is "Execute Docker command"
            - Step 4: Container running, output Result[2], using Final tool, instruction is empty

            ## User Goal
            {{goal}}

            ## Please Generate Plan
            First analyze the goal and clarify your thinking, then generate a structured execution plan.
        """,
    ),
}

EVALUATE_PLAN: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个计划评估器。
            请根据给定的计划，和当前计划执行的实际情况，分析当前计划是否合理和完整，并生成改进后的计划。

            # 一个好的计划应该：
            1. 能够成功完成用户的目标
            2. 计划中的每一个步骤必须且只能使用一个工具。
            3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
            4. 计划中的最后一步必须是Final工具，以确保计划执行结束。

            # 你此前的计划是：
            {{ plan }}

            # 这个计划的执行情况是：
            计划的执行情况将放置在<status></status> XML标签中。

            <status>
                {{ memory }}
            </status>

            # 进行评估时的注意事项：
            - 请一步一步思考，解析用户的目标，并指导你接下来的生成。思考过程应放置在<thinking></thinking> XML标签中。
            - 评估结果分为两个部分：
                - 计划评估的结论
                - 改进后的计划
            - 请按照以下JSON格式输出评估结果：

            ```json
            {
                "evaluation": "评估结果",
                "plans": [
                    {
                        "content": "改进后的计划内容",
                        "tool": "工具ID",
                        "instruction": "工具指令"
                    }
                ]
            }
            ```

            # 现在开始评估计划：
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a plan evaluator.
            Based on the given plan and the actual execution of the current plan, analyze whether the current plan is \
reasonable and complete, and generate an improved plan.

            # A good plan should:
            1. Be able to successfully achieve the user's goal.
            2. Each step in the plan must use only one tool.
            3. The steps in the plan must have clear and logical steps, without redundant or unnecessary steps.
            4. The last step in the plan must be a Final tool to ensure the completion of the plan execution.

            # Your previous plan was:
            {{ plan }}

            # The execution status of this plan is:
            The execution status of the plan will be placed in the <status></status> XML tags.

            <status>
                {{ memory }}
            </status>

            # Notes when conducting the evaluation:
            - Please think step by step, analyze the user's goal, and guide your subsequent generation. The thinking \
process should be placed in the <thinking></thinking> XML tags.
            - The evaluation results are divided into two parts:
                - Conclusion of the plan evaluation
                - Improved plan
            - Please output the evaluation results in the following JSON format:

            ```json
            {
                "evaluation": "Evaluation results",
                "plans": [
                    {
                        "content": "Improved plan content",
                        "tool": "Tool ID",
                        "instruction": "Tool instructions"
                    }
                ]
            }
            ```

            # Start evaluating the plan now:
        """,
    ),
}
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
            第{{ step_index }}步：{{ step_description }}
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
            Step {{ step_index }}: {{ step_description }}
            Called tool `{{ step_name }}` and provided parameters `{{ input_data | tojson }}`
            {% elif msg_type == "assistant" %}
            Step {{ step_index }} execution completed.
            Execution status: {{ step_status }}
            Got data: `{{ output_data | tojson }}`
            {% endif %}
        """,
    ),
}

MCP_FUNCTION_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            ## 任务描述

            你是一个专业的 MCP (Model Context Protocol) 选择器。
            你的任务是分析推理结果并选择最合适的 MCP 服务器 ID。

            ## 推理结果

            以下是需要分析的推理结果：

            ```
            {{ reasoning_result }}
            ```

            ## 可用的 MCP 服务器

            可选的 MCP 服务器 ID 列表：

            {% for mcp_id in mcp_ids %}
            - `{{ mcp_id }}`
            {% endfor %}

            ## 选择要求

            请仔细分析推理结果，选择最符合需求的 MCP 服务器。重点关注：

            1. **能力匹配**：推理中描述的能力需求与 MCP 服务器功能的对应关系
            2. **场景适配**：MCP 服务器是否适合当前应用场景
            3. **最优选择**：从可用列表中选择最合适的服务器 ID

            ## 输出格式

            请使用 `select_mcp` 工具进行选择，提供选中的 MCP 服务器 ID。
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            ## Task Description

            You are an expert MCP (Model Context Protocol) selector.
            Your task is to analyze the reasoning result and select the most appropriate MCP server ID.

            ## Reasoning Result

            Below is the reasoning result that needs to be analyzed:

            ```
            {{ reasoning_result }}
            ```

            ## Available MCP Servers

            List of available MCP server IDs:

            {% for mcp_id in mcp_ids %}
            - `{{ mcp_id }}`
            {% endfor %}

            ## Selection Requirements

            Please analyze the reasoning result carefully and select the MCP server that best matches the \
requirements. Focus on:

            1. **Capability Matching**: Align the capability requirements described in the reasoning with the MCP \
server functions
            2. **Scenario Fit**: Ensure the MCP server is suitable for the current application scenario
            3. **Optimal Choice**: Select the most appropriate server ID from the available list

            ## Output Format

            Please use the `select_mcp` tool to make your selection by providing the chosen MCP server ID.
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

FILL_PARAMS_QUERY: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            ## 当前目标

            {{ instruction }}

            ## 可用工具

            你可以使用 `{{ tool_name }}` 工具来完成上述目标。

            ### 工具信息
            - **工具名称**: `{{ tool_name }}`
            - **工具描述**: {{ tool_description }}

            ## 说明

            请调用上述工具来完成当前目标。注意事项：

            1. 仔细分析目标的具体要求，确保工具调用能达成预期结果
            2. 参考上下文信息，合理使用已有的结果和数据
            3. 提供所有必需信息，可选信息根据需要补充
            4. 必须至少选择1个工具进行调用
            5. 不要编造或假设不存在的信息
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            ## Current Objective

            {{ instruction }}

            ## Available Tool

            You can use the `{{ tool_name }}` tool to accomplish the above objective.

            ### Tool Information
            - **Tool Name**: `{{ tool_name }}`
            - **Tool Description**: {{ tool_description }}

            ## Instructions

            Please invoke the above tool to complete the current objective. Key points:

            1. Carefully analyze the objective requirements to ensure the tool invocation achieves the expected results
            2. Reference contextual information and reasonably use existing results and data
            3. Provide all required information, supplement optional information as needed
            4. Must invoke at least 1 tool
            5. Do not fabricate or assume non-existent information
        """,
    ),
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
        "examples": [
            {
                "plans": [
                    {
                        "content": "选择支持 Docker 的 MCP Server",
                        "tool": "mcp_selector",
                        "instruction": "需要支持 Docker 容器运行的 MCP Server",
                    },
                    {
                        "content": "基于 Result[0] 生成 Docker 命令",
                        "tool": "command_generator",
                        "instruction": "生成命令：后台运行 alpine:latest，挂载 /root 至 /data，执行 top",
                    },
                    {
                        "content": "在 Result[0] 上执行 Result[1] 的命令",
                        "tool": "command_executor",
                        "instruction": "执行 Docker 命令",
                    },
                    {
                        "content": "容器已运行，输出 Result[2]",
                        "tool": "Final",
                        "instruction": "",
                    },
                ],
            },
        ],
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
        "examples": [
            {
                "plans": [
                    {
                        "content": "Select MCP Server with Docker support",
                        "tool": "mcp_selector",
                        "instruction": "Need MCP Server supporting Docker container operation",
                    },
                    {
                        "content": "Generate Docker command based on Result[0]",
                        "tool": "command_generator",
                        "instruction": (
                            "Generate command: run alpine:latest in background, "
                            "mount /root to /data, execute top"
                        ),
                    },
                    {
                        "content": "Execute Result[1] command on Result[0]",
                        "tool": "command_executor",
                        "instruction": "Execute Docker command",
                    },
                    {
                        "content": "Container running, output Result[2]",
                        "tool": "Final",
                        "instruction": "",
                    },
                ],
            },
        ],
    },
}
