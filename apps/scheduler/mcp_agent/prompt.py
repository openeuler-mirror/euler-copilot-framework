# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""
from apps.schemas.enum_var import LanguageType
from textwrap import dedent

MCP_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个乐于助人的智能助手。
    你的任务是：根据当前目标，选择最合适的MCP Server。

    ## 选择MCP Server时的注意事项：

    1. 确保充分理解当前目标，选择最合适的MCP Server。
    2. 请在给定的MCP Server列表中选择，不要自己生成MCP Server。
    3. 请先给出你选择的理由，再给出你的选择。
    4. 当前目标将在下面给出，MCP Server列表也会在下面给出。
       请将你的思考过程放在"思考过程"部分，将你的选择放在"选择结果"部分。
    5. 选择必须是JSON格式，严格按照下面的模板，不要输出任何其他内容：

    ```json
    {
        "mcp": "你选择的MCP Server的名称"
    }
    ```

    6. 下面的示例仅供参考，不要将示例中的内容作为选择MCP Server的依据。

    ## 示例

    ### 目标

    我需要一个MCP Server来完成一个任务。

    ### MCP Server列表

    - **mcp_1**: "MCP Server 1"；MCP Server 1的描述
    - **mcp_2**: "MCP Server 2"；MCP Server 2的描述

    ### 请一步一步思考：

    因为当前目标需要一个MCP Server来完成一个任务，所以选择mcp_1。

    ### 选择结果

    ```json
    {
        "mcp": "mcp_1"
    }
    ```

    ## 现在开始！

    ### 目标

    {{goal}}

    ### MCP Server列表

    {% for mcp in mcp_list %}
    - **{{mcp.id}}**: "{{mcp.name}}"；{{mcp.description}}
    {% endfor %}

    ### 请一步一步思考：

    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are an intelligent assistant who is willing to help.
    Your task is: according to the current goal, select the most suitable MCP Server.

    ## Notes when selecting MCP Server:

    1. Make sure to fully understand the current goal and select the most suitable MCP Server.
    2. Please select from the given MCP Server list, do not generate MCP Server by yourself.
    3. Please first give your reason for selection, then give your selection.
    4. The current goal will be given below, and the MCP Server list will also be given below.
       Please put your thinking process in the "Thinking Process" part, and put your selection in the "Selection Result" part.
    5. The selection must be in JSON format, strictly follow the template below, do not output any other content:

    ```json
    {
        "mcp": "The name of the MCP Server you selected"
    }
    ```
    6. The example below is for reference only, do not use the content in the example as the basis for selecting MCP Server.

    ## Example

    ### Goal

    I need an MCP Server to complete a task.

    ### MCP Server List

    - **mcp_1**: "MCP Server 1"；Description of MCP Server 1
    - **mcp_2**: "MCP Server 2"；Description of MCP Server 2

    ### Please think step by step:

    Because the current goal needs an MCP Server to complete a task, so select mcp_1.

    ### Selection Result

    ```json
    {
        "mcp": "mcp_1"
    }
    ```

    ## Now start!
    ### Goal
                                
    {{goal}}

    ### MCP Server List

    {% for mcp in mcp_list %}
    - **{{mcp.id}}**: "{{mcp.name}}"；{{mcp.description}}
    {% endfor %}

    ### Please think step by step:
    """
    ),
}
TOOL_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个乐于助人的智能助手。
    你的任务是：根据当前目标，附加信息，选择最合适的MCP工具。
    ## 选择MCP工具时的注意事项：
    1. 确保充分理解当前目标，选择实现目标所需的MCP工具。
    2. 请在给定的MCP工具列表中选择，不要自己生成MCP工具。
    3. 可以选择一些辅助工具，但必须确保这些工具与当前目标相关。
    4. 注意，返回的工具ID必须是MCP工具的ID，而不是名称。
    5. 不要选择不存在的工具。
    必须按照以下格式生成选择结果，不要输出任何其他内容：
    ```json
    {
        "tool_ids": ["工具ID1", "工具ID2", ...]
    }
    ```

    # 示例
    ## 目标
    调优mysql性能
    ## MCP工具列表
    <tools>
    - <id>mcp_tool_1</id> <description>MySQL链接池工具；用于优化MySQL链接池</description>
    - <id>mcp_tool_2</id> <description>MySQL性能调优工具；用于分析MySQL性能瓶颈</description>
    - <id>mcp_tool_3</id> <description>MySQL查询优化工具；用于优化MySQL查询语句</description>
    - <id>mcp_tool_4</id> <description>MySQL索引优化工具；用于优化MySQL索引</description>
    - <id>mcp_tool_5</id> <description>文件存储工具；用于存储文件</description>
    - <id>mcp_tool_6</id> <description>mongoDB工具；用于操作MongoDB数据库</description>
    </tools>
    ## 附加信息
    1. 当前MySQL数据库的版本是8.0.26
    2. 当前MySQL数据库的配置文件路径是/etc/my.cnf，并含有以下配置项
    ```json
    {
        "max_connections": 1000,
        "innodb_buffer_pool_size": "1G",
        "query_cache_size": "64M"
    }
    ##输出
    ```json
    {
        "tool_ids": ["mcp_tool_1", "mcp_tool_2", "mcp_tool_3", "mcp_tool_4"]
    }
    ```
    # 现在开始！
    ## 目标
    {{goal}}
    ## MCP工具列表
    <tools>
    {% for tool in tools %}
    - <id>{{tool.id}}</id> <description>{{tool.name}}；{{tool.description}}</description>
    {% endfor %}
    </tools>
    ## 附加信息
    {{additional_info}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are an intelligent assistant who is willing to help.
    Your task is: according to the current goal, additional information, select the most suitable MCP tool.
    ## Notes when selecting MCP tool:
    1. Make sure to fully understand the current goal and select the MCP tool that can achieve the goal.
    2. Please select from the given MCP tool list, do not generate MCP tool by yourself.
    3. You can select some auxiliary tools, but you must ensure that these tools are related to the current goal.
    4. Note that the returned tool ID must be the ID of the MCP tool, not the name.
    5. Do not select non-existent tools.
    Must generate the selection result in the following format, do not output any other content:
    ```json
    {
        "tool_ids": ["tool_id1", "tool_id2", ...]
    }
    ```

    # Example
    ## Goal
    Optimize MySQL performance
    ## MCP Tool List
    <tools>
    - <id>mcp_tool_1</id> <description>MySQL connection pool tool；used to optimize MySQL connection pool</description>
    - <id>mcp_tool_2</id> <description>MySQL performance tuning tool；used to analyze MySQL performance bottlenecks</description>
    - <id>mcp_tool_3</id> <description>MySQL query optimization tool；used to optimize MySQL query statements</description>
    - <id>mcp_tool_4</id> <description>MySQL index optimization tool；used to optimize MySQL index</description>
    - <id>mcp_tool_5</id> <description>File storage tool；used to store files</description>
    - <id>mcp_tool_6</id> <description>MongoDB tool；used to operate MongoDB database</description>
    </tools>
    ## Additional Information
    1. The current MySQL database version is 8.0.26
    2. The current MySQL database configuration file path is /etc/my.cnf, and contains the following configuration items
    ```json
    {
        "max_connections": 1000,
        "innodb_buffer_pool_size": "1G",
        "query_cache_size": "64M"
    }
    ## Output
    ```json
    {
        "tool_ids": ["mcp_tool_1", "mcp_tool_2", "mcp_tool_3", "mcp_tool_4"]
    }
    ```
    # Now start!
    ## Goal
    {{goal}}
    ## MCP Tool List
    <tools>
    {% for tool in tools %}
    - <id>{{tool.id}}</id> <description>{{tool.name}}；{{tool.description}}</description>
    {% endfor %}
    </tools>
    ## Additional Information
    {{additional_info}}
    # Output
    """
    ),
}
EVALUATE_GOAL: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划评估器。
    请根据用户的目标和当前的工具集合以及一些附加信息，判断基于当前的工具集合，是否能够完成用户的目标。
    如果能够完成，请返回`true`，否则返回`false`。
    推理过程必须清晰明了，能够让人理解你的判断依据。
    必须按照以下格式回答：
    ```json
    {
        "can_complete": true/false,
        "resoning": "你的推理过程"
    }
    ```

    # 样例
    # 目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优

    # 工具集合
    你可以访问并使用一些工具，这些工具将在 <tools> </tools> XML标签中给出。
    <tools>
        - <id> mysql_analyzer </id> <description> 分析MySQL数据库性能 </description>
        - <id> performance_tuner </id> <description> 调优数据库性能 </description>
        - <id> Final </id> <description> 结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将作为最终结果。</description>
    </tools>

    # 附加信息
    1. 当前MySQL数据库的版本是8.0.26
    2. 当前MySQL数据库的配置文件路径是/etc/my.cnf

    ##
    ```json
    {
        "can_complete": true,
        "resoning": "当前的工具集合中包含mysql_analyzer和performance_tuner，能够完成对MySQL数据库的性能分析和调优，因此可以完成用户的目标。"
    }
    ```

    # 目标
    {{goal}}

    # 工具集合
    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        {% endfor %}
    </tools>

    # 附加信息
    {{additional_info}}

    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan evaluator.
    Please judge whether the current tool set can complete the user's goal based on the user's goal and the current tool set and some additional information.
    If it can be completed, return `true`, otherwise return `false`.
    The reasoning process must be clear and understandable, so that people can understand your judgment basis.
    Must answer in the following format:
    ```json
    {
        "can_complete": true/false,
        "resoning": "Your reasoning process"
    }
    ```

    # Example
    # Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.

    # Tool Set
    You can access and use some tools, which will be given in the <tools> </tools> XML tag.
    <tools>
        - <id> mysql_analyzer </id> <description> Analyze MySQL database performance </description>
        - <id> performance_tuner </id> <description> Tune database performance </description>
        - <id> Final </id> <description> End step, when executing this step, it means that the plan execution is over, and the result obtained will be the final result.</description>
    </tools>

    # Additional Information
    1. The current MySQL database version is 8.0.26
    2. The current MySQL database configuration file path is /etc/my.cnf

    ##
    ```json
    {
        "can_complete": true,
        "resoning": "The current tool set contains mysql_analyzer and performance_tuner, which can complete the performance analysis and optimization of MySQL database, so the user's goal can be completed."
    }
    ```

    # Goal
    {{goal}}

    # Tool Set
    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        {% endfor %}
    </tools>

    # Additional Information
    {{additional_info}}

    """
    ),
}
GENERATE_FLOW_NAME: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个智能助手，你的任务是根据用户的目标，生成一个合适的流程名称。

    # 生成流程名称时的注意事项：
    1. 流程名称应该简洁明了，能够准确表达达成用户目标的过程。
    2. 流程名称应该包含关键的操作或步骤，例如“扫描”、“分析”、“调优”等。
    3. 流程名称应该避免使用过于复杂或专业的术语，以便用户能够理解。
    4. 流程名称应该尽量简短，小于20个字或者单词。
    5. 只输出流程名称，不要输出其他内容。
    # 样例
    # 目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 输出
    {
        "flow_name": "扫描MySQL数据库并分析性能瓶颈，进行调优"
    }
    # 现在开始生成流程名称：
    # 目标
    {{goal}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are an intelligent assistant, your task is to generate a suitable flow name based on the user's goal.

    # Notes when generating flow names:
    1. The flow name should be concise and clear, accurately expressing the process of achieving the user's goal.
    2. The flow name should include key operations or steps, such as "scan", "analyze", "tune", etc.
    3. The flow name should avoid using overly complex or professional terms, so that users can understand.
    4. The flow name should be as short as possible, less than 20 characters or words.
    5. Only output the flow name, do not output other content.
    # Example
    # Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.
    # Output
    {
        "flow_name": "Scan MySQL database and analyze performance bottlenecks, and optimize it."
    }
    # Now start generating the flow name:
    # Goal
    {{goal}}
    # Output
    """
    ),
}
GET_REPLAN_START_STEP_INDEX: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个智能助手，你的任务是根据用户的目标、报错信息和当前计划和历史，获取重新规划的步骤起始索引。

    # 样例
    # 目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 报错信息
    执行端口扫描命令时，出现了错误：`- bash: curl: command not found`。
    # 当前计划
    ```json
    {
        "plans": [
            {
                "step_id": "step_1",
                "content": "生成端口扫描命令",
                "tool": "command_generator",
                "instruction": "生成端口扫描命令：扫描"
            },
            {
                "step_id": "step_2",
                "content": "在执行Result[0]生成的命令",
                "tool": "command_executor",
                "instruction": "执行端口扫描命令"
            }
        ]
    }
    # 历史
    [
        {
            id: "0",
            task_id: "task_1",
            flow_id: "flow_1",
            flow_name: "MYSQL性能调优",
            flow_status: "RUNNING",
            step_id: "step_1",
            step_name: "生成端口扫描命令",
            step_description: "生成端口扫描命令：扫描当前MySQL数据库的端口",
            step_status: "FAILED",
            input_data: {
                "command": "nmap -p 3306
                "target": "localhost"
            },
            output_data: {
                "error": "- bash: curl: command not found"
            }
        }
    ]
    # 输出
    {
        "start_index": 0,
        "reasoning": "当前计划的第一步就失败了，报错信息显示curl命令未找到，可能是因为没有安装curl工具，因此需要从第一步重新规划。"
    }
    # 现在开始获取重新规划的步骤起始索引：
    # 目标
    {{goal}}
    # 报错信息
    {{error_message}}
    # 当前计划
    {{current_plan}}
    # 历史
    {{history}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are an intelligent assistant, your task is to get the starting index of the step to be replanned based on the user's goal, error message, and current plan and history.

    # Example
    # Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.
    # Error message
    An error occurred while executing the port scan command: `- bash: curl: command not found`.
    # Current plan
    ```json
    {
        "plans": [
            {
                "step_id": "step_1",
                "content": "Generate port scan command",
                "tool": "command_generator",
                "instruction": "Generate port scan command: scan"
            },
            {
                "step_id": "step_2",
                "content": "Execute the command generated by Result[0]",
                "tool": "command_executor",
                "instruction": "Execute port scan command"
            }
        ]
    }
    # History
    [
        {
            id: "0",
            task_id: "task_1",
            flow_id: "flow_1",
            flow_name: "MYSQL Performance Tuning",
            flow_status: "RUNNING",
            step_id: "step_1",
            step_name: "Generate port scan command",
            step_description: "Generate port scan command: scan the port of the current MySQL database",
            step_status: "FAILED",
            input_data: {
                "command": "nmap -p 3306
                "target": "localhost"
            },
            output_data: {
                "error": "- bash: curl: command not found"
            }
        }
    ]
    # Output
    {
        "start_index": 0,
        "reasoning": "The first step of the current plan failed, the error message shows that the curl command was not found, which may be because the curl tool was not installed. Therefore, it is necessary to replan from the first step."
    }
    # Now start getting the starting index of the step to be replanned:
    # Goal
    {{goal}}
    # Error message
    {{error_message}}
    # Current plan
    {{current_plan}}
    # History
    {{history}}
    # Output
    """
    ),
}
CREATE_PLAN: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划生成器。
    请分析用户的目标，并生成一个计划。你后续将根据这个计划，一步一步地完成用户的目标。

    # 一个好的计划应该：

    1. 能够成功完成用户的目标
    2. 计划中的每一个步骤必须且只能使用一个工具。
    3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
    4. 计划中的最后一步必须是Final工具，以确保计划执行结束。

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

    - 在生成计划之前，请一步一步思考，解析用户的目标，并指导你接下来的生成。
思考过程应放置在 <thinking> </thinking> XML标签中。
    - 计划内容中，可以使用"Result[]"来引用之前计划步骤的结果。例如："Result[3]"表示引用第三条计划执行后的结果。
    - 计划不得多于{{max_num}}条，且每条计划内容应少于150字。

    # 工具

    你可以访问并使用一些工具，这些工具将在 <tools> </tools> XML标签中给出。

    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        {% endfor %}
    </tools>

    # 样例

    # 目标

    在后台运行一个新的alpine: latest容器，将主机/root文件夹挂载至/data，并执行top命令。

    # 计划

    <thinking>
    1. 这个目标需要使用Docker来完成, 首先需要选择合适的MCP Server
    2. 目标可以拆解为以下几个部分:
       - 运行alpine: latest容器
       - 挂载主机目录
       - 在后台运行
       - 执行top命令
    3. 需要先选择MCP Server, 然后生成Docker命令, 最后执行命令
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

    # 目标

    {{goal}}

    # 计划
"""
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan builder.
    Analyze the user's goals and generate a plan. You will then follow this plan, step by step, to achieve the user's goals.

    # A good plan should:

    1. Be able to successfully achieve the user's goals.
    2. Each step in the plan must use only one tool.
    3. The steps in the plan must have clear and logical progression, without redundant or unnecessary steps.
    4. The last step in the plan must be the Final tool to ensure the plan execution is complete.

    # Things to note when generating a plan:

    - Each plan contains 3 parts:
        - Plan content: describes the general content of a single plan step
        - Tool ID: must be selected from the tool list below
        - Tool instructions: rewrite the user's goal to make it more consistent with the tool's input requirements
    - The plan must be generated in the following format, and no additional data should be output:

    ```json
    {
        "plans": [
            {
                "content": "Plan content",
                "tool": "Tool ID",
                "instruction": "Tool instruction"
            }
        ]
    }
    ```

    - Before generating a plan, please think step by step, analyze the user's goals, and guide your subsequent generation.
    The thinking process should be placed in the <thinking> </thinking> XML tags.
    - In the plan content, you can use "Result[]" to reference the results of the previous plan step. For example: "Result[3]" refers to the result after the third plan is executed.
    - There should be no more than {{max_num}} plans, and each plan content should be less than 150 words.

    # Tools

    You can access and use a number of tools, listed within the <tools> </tools> XML tags.

    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}; {{tool.description}} </description>
        {% endfor %}
    </tools>

    # Example

    # Goal

    Run a new alpine:latest container in the background, mount the host's /root folder to /data, and execute the top command.

    # Plan

    <thinking>
    1. This goal needs to be completed using Docker. First, you need to select a suitable MCP Server.
    2. The goal can be broken down into the following parts:
        - Run the alpine:latest container
        - Mount the host directory
        - Run in the background
        - Execute the top command
    3. You need to select the MCP Server first, then generate the Docker command, and finally execute the command.
    </thinking> 
    ```json
    {
        "plans": [
            {
                "content": "Select an MCP Server that supports Docker",
                "tool": "mcp_selector",
                "instruction": "You need an MCP Server that supports running Docker containers"
            },
            {
                "content": "Use the MCP Server selected in Result[0] to generate Docker commands",
                "tool": "command_generator",
                "instruction": "Generate Docker commands: run the alpine:latest container in the background, mount /root to /data, and execute the top command"
            },
            {
                "content": "In the MCP of Result[0] Execute the command generated by Result[1] on the server",
                "tool": "command_executor",
                "instruction": "Execute Docker command"
            },
            {
                "content": "Task execution completed, the container is running in the background, the result is Result[2]",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    ```

    # Now start generating the plan:

    # Goal

    {{goal}}

    # Plan
    """
    ),
}
RECREATE_PLAN: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划重建器。
    请根据用户的目标、当前计划和运行报错，重新生成一个计划。

    # 一个好的计划应该：

    1. 能够成功完成用户的目标
    2. 计划中的每一个步骤必须且只能使用一个工具。
    3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
    4. 你的计划必须避免之前的错误，并且能够成功执行。
    5. 计划中的最后一步必须是Final工具，以确保计划执行结束。

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

    - 在生成计划之前，请一步一步思考，解析用户的目标，并指导你接下来的生成。
思考过程应放置在 <thinking> </thinking> XML标签中。
    - 计划内容中，可以使用"Result[]"来引用之前计划步骤的结果。例如："Result[3]"表示引用第三条计划执行后的结果。
    - 计划不得多于{{max_num}}条，且每条计划内容应少于150字。

    # 样例

    # 目标

    请帮我扫描一下192.168.1.1的这台机器的端口，看看有哪些端口开放。
    # 工具
    你可以访问并使用一些工具，这些工具将在 <tools> </tools> XML标签中给出。
    <tools>
        - <id> command_generator </id> <description> 生成命令行指令 </description>
        - <id> tool_selector </id> <description> 选择合适的工具 </description>
        - <id> command_executor </id> <description> 执行命令行指令 </description>
        - <id> Final </id> <description> 结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将作为最终结果。</description>
    </tools>     # 当前计划
    ```json
    {
        "plans": [
            {
                "content": "生成端口扫描命令",
                "tool": "command_generator",
                "instruction": "生成端口扫描命令：扫描192.168.1.1的开放端口"
            },
            {
                "content": "在执行第一步生成的命令",
                "tool": "command_executor",
                "instruction": "执行端口扫描命令"
            },
            {
                "content": "任务执行完成",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    ```
    # 运行报错
    执行端口扫描命令时，出现了错误：`- bash: curl: command not found`。
    # 重新生成的计划

    <thinking>
    1. 这个目标需要使用网络扫描工具来完成, 首先需要选择合适的网络扫描工具
    2. 目标可以拆解为以下几个部分:
        - 生成端口扫描命令
        - 执行端口扫描命令
    3.但是在执行端口扫描命令时，出现了错误：`- bash: curl: command not found`。
    4.我将计划调整为：
        - 需要先生成一个命令，查看当前机器支持哪些网络扫描工具
        - 执行这个命令，查看当前机器支持哪些网络扫描工具
        - 然后从中选择一个网络扫描工具
        - 基于选择的网络扫描工具，生成端口扫描命令
        - 执行端口扫描命令
    </thinking> ```json
    {
        "plans": [
            {
                "content": "需要生成一条命令查看当前机器支持哪些网络扫描工具",
                "tool": "command_generator",
                "instruction": "选择一个前机器支持哪些网络扫描工具"
            },
            {
                "content": "执行第一步中生成的命令，查看当前机器支持哪些网络扫描工具",
                "tool": "command_executor",
                "instruction": "执行第一步中生成的命令"
            },
            {
                "content": "从第二步执行结果中选择一个网络扫描工具，生成端口扫描命令",
                "tool": "tool_selector",
                "instruction": "选择一个网络扫描工具，生成端口扫描命令"
            },
            {
                "content": "基于第三步中选择的网络扫描工具，生成端口扫描命令",
                "tool": "command_generator",
                "instruction": "生成端口扫描命令：扫描192.168.1.1的开放端口"
            },
            {
                "content": "执行第四步中生成的端口扫描命令",
                "tool": "command_executor",
                "instruction": "执行端口扫描命令"
            },
            {
                "content": "任务执行完成",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    ```

    # 现在开始重新生成计划：

    # 目标

    {{goal}}

    # 工具

    你可以访问并使用一些工具，这些工具将在 <tools> </tools> XML标签中给出。

    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        {% endfor %}
    </tools>

    # 当前计划
    {{current_plan}}

    # 运行报错
    {{error_message}}

    # 重新生成的计划
"""
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan rebuilder.
    Please regenerate a plan based on the user's goals, current plan, and runtime errors.

    # A good plan should:

    1. Successfully achieve the user's goals.
    2. Each step in the plan must use only one tool.
    3. The steps in the plan must have clear and logical progression, without redundant or unnecessary steps.
    4. Your plan must avoid previous errors and be able to be successfully executed.
    5. The last step in the plan must be the Final tool to ensure that the plan is complete.

    # Things to note when generating a plan:

    - Each plan contains 3 parts:
        - Plan content: describes the general content of a single plan step
        - Tool ID: must be selected from the tool list below
        - Tool instructions: rewrite the user's goal to make it more consistent with the tool's input requirements
    - The plan must be generated in the following format, and no additional data should be output:

    ```json
    {
        "plans": [
            {
                "content": "Plan content",
                "tool": "Tool ID",
                "instruction": "Tool instruction"
            }
        ]
    }
    ```

    - Before generating a plan, please think step by step, analyze the user's goals, and guide your subsequent generation.
    The thinking process should be placed in the <thinking> </thinking> XML tags.
    - In the plan content, you can use "Result[]" to reference the results of the previous plan step. For example: "Result[3]" refers to the result after the third plan is executed.
    - There should be no more than {{max_num}} plans, and each plan content should be less than 150 words.

    # Objective

    Please scan the ports of the machine at 192.168.1.1 to see which ports are open.
    # Tools
    You can access and use a number of tools, which are listed within the <tools> </tools> XML tags.
    <tools>
        - <id> command_generator </id> <description> Generates command line instructions </description>
        - <id> tool_selector </id> <description> Selects the appropriate tool </description>
        - <id> command_executor </id> <description> Executes command line instructions </description>
        - <id> Final </id> <description> This is the final step. When this step is reached, the plan execution ends, and the result is used as the final result. </description>
    </tools> # Current plan
    ```json
    {
        "plans": [
            {
                "content": "Generate port scan command",
                "tool": "command_generator",
                "instruction": "Generate port scan command: Scan open ports on 192.168.1.1"
            },
            {
                "content": "Execute the command generated in the first step",
                "tool": "command_executor",
                "instruction": "Execute the port scan command"
            },
            {
                "content": "Task execution completed",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    ```
    # Run error
    When executing the port scan command, an error occurred: `- bash: curl: command not found`.
    # Regenerate the plan

    <thinking>
    1. This goal requires a network scanning tool. First, select the appropriate network scanning tool.
    2. The goal can be broken down into the following parts:
        - Generate the port scanning command
        - Execute the port scanning command
    3. However, when executing the port scanning command, an error occurred: `- bash: curl: command not found`.
    4. I adjusted the plan to:
        - Generate a command to check which network scanning tools the current machine supports
        - Execute this command to check which network scanning tools the current machine supports
        - Then select a network scanning tool
        - Generate a port scanning command based on the selected network scanning tool
        - Execute the port scanning command
    </thinking> ```json
    {
        "plans": [
            {
                "content": "You need to generate a command to check which network scanning tools the current machine supports",
                "tool": "command_generator",
                "instruction": "Select which network scanning tools the current machine supports"

            },
            {
                "content": "Execute the command generated in the first step to check which network scanning tools the current machine supports",
                "tool": "command_executor",
                "instruction": "Execute the command generated in the first step"

            },
            {
                "content": "Select a network scanning tool from the results of the second step and generate a port scanning command",
                "tool": "tool_selector",
                "instruction": "Select a network scanning tool and generate a port scanning command"

            },
            {
                "content": "Generate a port scan command based on the network scanning tool selected in step 3",
                "tool": "command_generator",
                "instruction": "Generate a port scan command: Scan the open ports on 192.168.1.1"
            },
            {
                "content": "Execute the port scan command generated in step 4",
                "tool": "command_executor",
                "instruction": "Execute the port scan command"
            },
            {
                "content": "Task execution completed",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    ```

    # Now start regenerating the plan:

    # Goal

    {{goal}}

    # Tools

    You can access and use a number of tools, which are listed within the <tools> </tools> XML tags.

    <tools>
        {% for tool in tools %}
        - <id> {{tool.id}} </id> <description> {{tool.name}}; {{tool.description}} </description>
        {% endfor %}
    </tools>

    # Current plan
    {{current_plan}}

    # Run error
    {{error_message}}

    # Regenerated plan
    """
    ),
}
GEN_STEP: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划生成器。
    请根据用户的目标、当前计划和历史，生成一个新的步骤。

    # 一个好的计划步骤应该：
    1.使用最适合的工具来完成当前步骤。
    2.能够基于当前的计划和历史，完成阶段性的任务。
    3.不要选择不存在的工具。
    4.如果你认为当前已经达成了用户的目标，可以直接返回Final工具，表示计划执行结束。

    # 样例 1
    # 目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优,我的ip是192.168.1.1，数据库端口是3306，用户名是root，密码是password
    # 历史记录
    第1步：生成端口扫描命令
      - 调用工具 `command_generator`，并提供参数 `帮我生成一个mysql端口扫描命令`
      - 执行状态：成功
      - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
    第2步：执行端口扫描命令
        - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"result": "success"}`
    # 工具
    <tools>
    - <id>mcp_tool_1</id> <description>mysql_analyzer；用于分析数据库性能/description>
    - <id>mcp_tool_2</id> <description>文件存储工具；用于存储文件</description>
    - <id>mcp_tool_3</id> <description>mongoDB工具；用于操作MongoDB数据库</description>
    - <id>Final</id> <description>结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将作为最终结果。</description>
    </tools>
    # 输出
    ```json
    {
        "tool_id": "mcp_tool_1", // 选择的工具ID
        "description": "扫描ip为192.168.1.1的MySQL数据库，端口为3306，用户名为root，密码为password的数据库性能",
    }
    ```
    # 样例二
    # 目标
    计划从杭州到北京的旅游计划
    # 历史记录
    第1步：将杭州转换为经纬度坐标
      - 调用工具 `maps_geo_planner`，并提供参数 `{"city_from": "杭州", "address": "西湖"}`
      - 执行状态：成功
      - 得到数据：`{"location": "123.456, 78.901"}`
    第2步：查询杭州的天气
        - 调用工具 `weather_query`，并提供参数 `{"location": "123.456, 78.901"}`
        - 执行状态：成功
        - 得到数据：`{"weather": "晴", "temperature": "25°C"}`
    第3步：将北京转换为经纬度坐标
        - 调用工具 `maps_geo_planner`，并提供参数 `{"city_from": "北京", "address": "天安门"}`
        - 执行状态：成功
        - 得到数据：`{"location": "123.456, 78.901"}`
    第4步：查询北京的天气
        - 调用工具 `weather_query`，并提供参数 `{"location": "123.456, 78.901"}`
        - 执行状态：成功
        - 得到数据：`{"weather": "晴", "temperature": "25°C"}`
    # 工具
    <tools>
    - <id>mcp_tool_4</id> <description>maps_geo_planner；将详细的结构化地址转换为经纬度坐标。支持对地标性名胜景区、建筑物名称解析为经纬度坐标</description>
    - <id>mcp_tool_5</id> <description>weather_query；天气查询，用于查询天气信息</description>
    - <id>mcp_tool_6</id> <description>maps_direction_transit_integrated；根据用户起终点经纬度坐标规划综合各类公共（火车、公交、地铁）交通方式的通勤方案，并且返回通勤方案的数据，跨城场景下必须传起点城市与终点城市</description>
    - <id>Final</id> <description>Final；结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将作为最终结果。</description>
    </tools>
    # 输出
    ```json
    {
        "tool_id": "mcp_tool_6", // 选择的工具ID
        "description": "规划从杭州到北京的综合公共交通方式的通勤方案"
    }
    ```
    # 现在开始生成步骤：
    # 目标
    {{goal}}
    # 历史记录
    {{history}}
    # 工具
    <tools>
    {% for tool in tools %}
    - <id>{{tool.id}}</id> <description>{{tool.name}}；{{tool.description}}</description>
    {% endfor %}
    </tools>
"""
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan generator.
    Please generate a new step based on the user's goal, current plan, and history.

    # A good plan step should:
    1. Use the most appropriate tool for the current step.
    2. Complete the tasks at each stage based on the current plan and history.
    3. Do not select a tool that does not exist.
    4. If you believe the user's goal has been achieved, return to the Final tool to complete the plan execution.

    # Example 1
    # Objective
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it. My IP address is 192.168.1.1, the database port is 3306, my username is root, and my password is password.
    # History
    Step 1: Generate a port scan command
        - Call the `command_generator` tool and provide the `help me generate a MySQL port scan command` parameter.
        - Execution status: Success.
        - Result: `{"command": "nmap -sS -p --open 192.168.1.1"}`
    Step 2: Execute the port scan command
        - Call the `command_executor` tool and provide the `{"command": "nmap -sS -p --open 192.168.1.1"}` parameter.
        - Execution status: Success.
        - Result: `{"result": "success"}`
    # Tools
    <tools>
        - <id>mcp_tool_1</id> <description>mysql_analyzer; used for analyzing database performance.
        - <id>mcp_tool_2</id> <description>File storage tool; used for storing files.
        - <id>mcp_tool_3</id> <description>MongoDB tool; used for operating MongoDB databases.
        - <id>Final</id> <description>This step completes the plan execution and the result is used as the final result. </description>
    </tools>
    # Output
    ```json
    {
        "tool_id": "mcp_tool_1", // Selected tool ID
        "description": "Scan the database performance of the MySQL database with IP address 192.168.1.1, port 3306, username root, and password password",
    }
    ```
    # Example 2
    # Objective
    Plan a trip from Hangzhou to Beijing
    # History
    Step 1: Convert Hangzhou to latitude and longitude coordinates
        - Call the `maps_geo_planner` tool and provide `{"city_from": "Hangzhou", "address": "West Lake"}`
        - Execution status: Success
        - Result: `{"location": "123.456, 78.901"}`
    Step 2: Query the weather in Hangzhou
        - Call the `weather_query` tool and provide `{"location": "123.456, 78.901"}`
        - Execution Status: Success
        - Result: `{"weather": "Sunny", "temperature": "25°C"}`
    Step 3: Convert Beijing to latitude and longitude coordinates
        - Call the `maps_geo_planner` tool and provide `{"city_from": "Beijing", "address": "Tiananmen"}`
        - Execution Status: Success
        - Result: `{"location": "123.456, 78.901"}`
    Step 4: Query the weather in Beijing
        - Call the `weather_query` tool and provide `{"location": "123.456, 78.901"}`
        - Execution Status: Success
        - Result: `{"weather": "Sunny", "temperature": "25°C"}`
    # Tools
    <tools>
        - <id>mcp_tool_4</id> <description>maps_geo_planner; Converts a detailed structured address into longitude and latitude coordinates. Supports parsing landmarks, scenic spots, and building names into longitude and latitude coordinates.</description>
        - <id>mcp_tool_5</id> <description>weather_query; Weather query, used to query weather information.</description>
        - <id>mcp_tool_6</id> <description>maps_direction_transit_integrated; Plans a commuting plan based on the user's starting and ending longitude and latitude coordinates, integrating various public transportation modes (train, bus, subway), and returns the commuting plan data. For cross-city scenarios, both the starting and ending cities must be provided.</description>
        - <id>Final</id> <description>Final; Final step. When this step is reached, plan execution is complete, and the resulting result is used as the final result. </description>
    </tools>
    # Output
    ```json
    {
        "tool_id": "mcp_tool_6", // Selected tool ID
        "description": "Plan a comprehensive public transportation commute from Hangzhou to Beijing"
    }
    ```
    # Now start generating steps:
    # Goal
    {{goal}}
    # History
    {{history}}
    # Tools
    <tools>
    {% for tool in tools %}
        - <id>{{tool.id}}</id> <description>{{tool.name}}；{{tool.description}}</description>
    {% endfor %}
    </tools>
    """
    ),
}

TOOL_SKIP: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划执行器。
    你的任务是根据当前的计划和用户目标，判断当前步骤是否需要跳过。
    如果需要跳过，请返回`true`，否则返回`false`。
    必须按照以下格式回答：
    ```json
    {
        "skip": true/false,
    }
    ```
    注意：
    1.你的判断要谨慎，在历史消息中有足够的上下文信息时，才可以判断是否跳过当前步骤。
    # 样例
    # 用户目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 历史
    第1步：生成端口扫描命令
      - 调用工具 `command_generator`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
    第2步：执行端口扫描命令
        - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"result": "success"}`
    第3步：分析端口扫描结果
        - 调用工具 `mysql_analyzer`，并提供参数 `{"host": "192.168.1.1", "port": 3306, "username": "root", "password": "password"}`
        - 执行状态：成功
        - 得到数据：`{"performance": "good", "bottleneck": "none"}`
    # 当前步骤
    <step>
        <step_id> step_4 </step_id>
        <step_name> command_generator </step_name>
        <step_instruction> 生成MySQL性能调优命令 </step_instruction>
        <step_content> 生成MySQL性能调优命令：调优MySQL数据库性能 </step_content>
    </step>
    # 输出
    ```json
    {
        "skip": true
    }
    ```
    # 用户目标
    {{goal}}
    # 历史
    {{history}}
    # 当前步骤
    <step>
        <step_id> {{step_id}} </step_id>
        <step_name> {{step_name}} </step_name>
        <step_instruction> {{step_instruction}} </step_instruction>
        <step_content> {{step_content}} </step_content>
    </step>
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan executor.
    Your task is to determine whether the current step should be skipped based on the current plan and the user's goal.
    If skipping is required, return `true`; otherwise, return `false`.
    The answer must follow the following format:
    ```json
    {
        "skip": true/false,
    }
    ```
    Note:
    1. Be cautious in your judgment and only decide whether to skip the current step when there is sufficient context in the historical messages.
    # Example
    # User Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.
    # History
    Step 1: Generate a port scan command
        - Call the `command_generator` tool with `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - Execution Status: Success
        - Result: `{"command": "nmap -sS -p--open 192.168.1.1"}`
    Step 2: Execute the port scan command
        - Call the `command_executor` tool with `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - Execution Status: Success
        - Result: `{"result": "success"}`
    Step 3: Analyze the port scan results
        - Call the `mysql_analyzer` tool with `{"host": "192.168.1.1", "port": 3306, "username": "root", "password": "password"}`
        - Execution status: Success
        - Result: `{"performance": "good", "bottleneck": "none"}`
    # Current step
    <step>
    <step_id> step_4 </step_id>
    <step_name> command_generator </step_name>
    <step_instruction> Generate MySQL performance tuning commands </step_instruction>
    <step_content> Generate MySQL performance tuning commands: Tune MySQL database performance </step_content>
    </step>
    # Output
    ```json
    {
        "skip": true
    }
    ```
    # User goal
    {{goal}}
    # History
    {{history}}
    # Current step
    <step>
    <step_id> {{step_id}} </step_id>
    <step_name> {{step_name}} </step_name> 
    <step_instruction> {{step_instruction}} </step_instruction> 
    <step_content> {{step_content}} </step_content> 
    </step> 
    # output 
    """
    ),
}
RISK_EVALUATE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个工具执行计划评估器。
    你的任务是根据当前工具的名称、描述和入参以及附加信息，判断当前工具执行的风险并输出提示。
    ```json
    {
        "risk": "low/medium/high",
        "reason": "提示信息"
    }
    ```
    # 样例
    # 工具名称
    mysql_analyzer
    # 工具描述
    分析MySQL数据库性能
    # 工具入参
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # 附加信息
    1. 当前MySQL数据库的版本是8.0.26
    2. 当前MySQL数据库的配置文件路径是/etc/my.cnf，并含有以下配置项
    ```ini
    [mysqld]
    innodb_buffer_pool_size=1G
    innodb_log_file_size=256M
    ```
    # 输出
    ```json
    {
        "risk": "中",
        "reason": "当前工具将连接到MySQL数据库并分析性能，可能会对数据库性能产生一定影响。请确保在非生产环境中执行此操作。"
    }
    ```
    # 工具
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # 工具入参
    {{input_param}}
    # 附加信息
    {{additional_info}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a tool execution plan evaluator.
    Your task is to determine the risk of executing the current tool based on its name, description, input parameters, and additional information, and output a warning.
    ```json
    {
        "risk": "low/medium/high",
        "reason": "prompt message"
    }
    ```
    # Example
    # Tool name
    mysql_analyzer
    # Tool description
    Analyzes MySQL database performance
    # Tool input
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # Additional information
    1. The current MySQL database version is 8.0.26
    2. The current MySQL database configuration file path is /etc/my.cnf and contains the following configuration items
    ```ini
    [mysqld]
    innodb_buffer_pool_size=1G
    innodb_log_file_size=256M
    ```
    # Output
    ```json
    {
        "risk": "medium",
        "reason": "This tool will connect to a MySQL database and analyze performance, which may impact database performance. This operation should only be performed in a non-production environment."
    }
    ```
    # Tool
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # Tool Input Parameters
    {{input_param}}
    # Additional Information
    {{additional_info}}
    # Output

    """
    ),
}
# 根据当前计划和报错信息决定下一步执行，具体计划有需要用户补充工具入参、重计划当前步骤、重计划接下来的所有计划
TOOL_EXECUTE_ERROR_TYPE_ANALYSIS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划决策器。

    你的任务是根据用户目标、当前计划、当前使用的工具、工具入参和工具运行报错，决定下一步执行的操作。
    请根据以下规则进行判断：
    1. 仅通过补充工具入参来解决问题的，返回 missing_param;
    2. 需要重计划当前步骤的，返回 decorrect_plan
    3.推理过程必须清晰明了，能够让人理解你的判断依据，并且不超过100字。
    你的输出要以json格式返回，格式如下：

    ```json
    {
        "error_type": "missing_param/decorrect_plan,
        "reason": "你的推理过程"
    }
    ```

    # 样例
    # 用户目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 当前计划
    {
        "plans": [
            {
                "content": "生成端口扫描命令",
                "tool": "command_generator",
                "instruction": "生成端口扫描命令：扫描192.168.1.1的开放端口"
            },
            {
                "content": "在执行Result[0]生成的命令",
                "tool": "command_executor",
                "instruction": "执行端口扫描命令"
            },
            {
                "content": "任务执行完成，端口扫描结果为Result[2]",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    # 当前使用的工具
    <tool>
        <name> command_executor </name>
        <description> 执行命令行指令 </description>
    </tool>
    # 工具入参
    {
        "command": "nmap -sS -p--open 192.168.1.1"
    }
    # 工具运行报错
    执行端口扫描命令时，出现了错误：`- bash: nmap: command not found`。
    # 输出
    ```json
    {
        "error_type": "decorrect_plan",
        "reason": "当前计划的第二步执行失败，报错信息显示nmap命令未找到，可能是因为没有安装nmap工具，因此需要重计划当前步骤。"
    }
    ```
    # 用户目标
    {{goal}}
    # 当前计划
    {{current_plan}}
    # 当前使用的工具
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # 工具入参
    {{input_param}}
    # 工具运行报错
    {{error_message}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan decider.

    Your task is to decide the next action based on the user's goal, the current plan, the tool being used, tool inputs, and tool errors.
    Please make your decision based on the following rules:
    1. If the problem can be solved by simply adding tool inputs, return missing_param;
    2. If the current step needs to be replanned, return decorrect_plan.
    3. Your reasoning must be clear and concise, allowing the user to understand your decision. It should not exceed 100 words.
    Your output should be returned in JSON format, as follows:

    ```json
    {
        "error_type": "missing_param/decorrect_plan,
        "reason": "Your reasoning"
    }
    ```

    # Example
    # User Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.
    # Current Plan
    {
        "plans": [
            {
                "content": "Generate port scan command",
                "tool": "command_generator",
                "instruction": "Generate port scan command: Scan the open ports of 192.168.1.1"
            },
            {
                "content": "Execute the command generated by Result[0]",
                "tool": "command_executor",
                "instruction": "Execute the port scan command"
            },
            {
                "content": "Task execution completed, the port scan result is Result[2]",
                "tool": "Final",
                "instruction": ""
            }
        ]
    }
    # Currently used tool
    <tool>
        <name> command_executor </name>
        <description> Execute command line instructions </description>
    </tool>
    # Tool input parameters
    {
        "command": "nmap -sS -p--open 192.168.1.1"
    }
    # Tool running error
    When executing the port scan command, an error occurred: `- bash: nmap: command not found`.
    # Output
    ```json
    {
        "error_type": "decorrect_plan",
        "reason": "The second step of the current plan failed. The error message shows that the nmap command was not found. This may be because the nmap tool is not installed. Therefore, the current step needs to be replanned."
    }
    ```
    # User goal
    {{goal}}
    # Current plan
    {{current_plan}}
    # Currently used tool
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # Tool input parameters
    {{input_param}}
    # Tool execution error
    {{error_message}}
    # Output
    """
    ),
}

IS_PARAM_ERROR: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个计划执行专家，你的任务是判断当前的步骤执行失败是否是因为参数错误导致的，
    如果是，请返回`true`，否则返回`false`。
    必须按照以下格式回答：
    ```json
    {
        "is_param_error": true/false,
    }
    ```
    # 样例
    # 用户目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 历史
    第1步：生成端口扫描命令
      - 调用工具 `command_generator`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
    第2步：执行端口扫描命令
        - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"result": "success"}`
    # 当前步骤
    <step>
        <step_id> step_3 </step_id>
        <step_name> mysql_analyzer </step_name>
        <step_instruction> 分析MySQL数据库性能 </step_instruction>
    </step>
    # 工具入参
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # 工具运行报错
    执行MySQL性能分析命令时，出现了错误：`host is not correct`。

    # 输出
    ```json
    {
        "is_param_error": true
    }
    ```
    # 用户目标
    {{goal}}
    # 历史
    {{history}}
    # 当前步骤
    <step>
        <step_id> {{step_id}} </step_id>
        <step_name> {{step_name}} </step_name>
        <step_instruction> {{step_instruction}} </step_instruction>
    </step>
    # 工具入参
    {{input_param}}
    # 工具运行报错
    {{error_message}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a plan execution expert. Your task is to determine whether the current step execution failure is due to parameter errors.
    If so, return `true`; otherwise, return `false`.
    The answer must be in the following format:
    ```json
    {
        "is_param_error": true/false,
    }
    ```
    # Example
    # User Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.
    # History
    Step 1: Generate a port scan command
        - Call the `command_generator` tool and provide `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - Execution Status: Success
        - Result: `{"command": "nmap -sS -p--open 192.168.1.1"}`
    Step 2: Execute the port scan command
        - Call the `command_executor` tool and provide `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - Execution Status: Success
        - Result: `{"result": "success"}`
    # Current step
    <step>
    <step_id> step_3 </step_id>
    <step_name> mysql_analyzer </step_name>
    <step_instruction> Analyze MySQL database performance </step_instruction>
    </step>
    # Tool input parameters
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # Tool execution error
    When executing the MySQL performance analysis command, an error occurred: `host is not correct`.

    # Output
    ```json
    {
        "is_param_error": true
    }
    ```
    # User goal
    {{goal}}
    # History
    {{history}}
    # Current step
    <step>
    <step_id> {{step_id}} </step_id>
    <step_name> {{step_name}} </step_name>
    <step_instruction> {{step_instruction}} </step_instruction>
    </step>
    # Tool input parameters
    {{input_param}}
    # Tool error
    {{error_message}}
    # Output
    """
    ),
}

# 将当前程序运行的报错转换为自然语言
CHANGE_ERROR_MESSAGE_TO_DESCRIPTION: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个智能助手，你的任务是将当前程序运行的报错转换为自然语言描述。
    请根据以下规则进行转换：
    1. 将报错信息转换为自然语言描述，描述应该简洁明了，能够让人理解报错的原因和影响。
    2. 描述应该包含报错的具体内容和可能的解决方案。
    3. 描述应该避免使用过于专业的术语，以便用户能够理解。
    4. 描述应该尽量简短，控制在50字以内。
    5. 只输出自然语言描述，不要输出其他内容。
    # 样例
    # 工具信息
    <tool>
        <name> port_scanner </name>
        <description> 扫描主机端口 </description>
        <input_schema>
        {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机地址"
                },
                "port": {
                    "type": "integer",
                    "description": "端口号"
                },
                "username": {
                    "type": "string",
                    "description": "用户名"
                },
                "password": {
                    "type": "string",
                    "description": "密码" 
                }
            },
            "required": ["host", "port", "username", "password"]
        }
        </input_schema>
    </tool>
    # 工具入参
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # 报错信息
    执行端口扫描命令时，出现了错误：`password is not correct`。
    # 输出
    扫描端口时发生错误：密码不正确。请检查输入的密码是否正确，并重试。
    # 现在开始转换报错信息：
    # 工具信息
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
        <input_schema>
        {{input_schema}}
        </input_schema>
    </tool>
    # 工具入参
    {{input_params}}
    # 报错信息
    {{error_message}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are an intelligent assistant. Your task is to convert the error message generated by the current program into a natural language description.
    Please follow the following rules for conversion:
    1. Convert the error message into a natural language description. The description should be concise and clear, allowing users to understand the cause and impact of the error.
    2. The description should include the specific content of the error and possible solutions.
    3. The description should avoid using overly technical terms so that users can understand it.
    4. The description should be as brief as possible, within 50 words.
    5. Only output the natural language description, do not output other content.
    # Example
    # Tool Information
    <tool>
        <name> port_scanner </name>
        <description> Scan host ports </description>
        <input_schema>
        {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Host address"
                },
                "port": {
                    "type": "integer",
                    "description": "Port number"
                },
                "username": {
                    "type": "string",
                    "description": "Username"
                },
                "password": {
                    "type": "string",
                    "description": "Password"
                }
            },
            "required": ["host", "port", "username", "password"]
        }
        </input_schema>
    </tool>
    # Tool input
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # Error message
    An error occurred while executing the port scan command: `password is not correct`.
    # Output
    An error occurred while scanning the port: The password is incorrect. Please check that the password you entered is correct and try again.
    # Now start converting the error message:
    # Tool information
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
        <input_schema>
        {{input_schema}}
        </input_schema>
    </tool>
    # Tool input parameters
    {{input_params}}
    # Error message
    {{error_message}}
    # Output
    """
    ),
}
# 获取缺失的参数的json结构体
GET_MISSING_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个工具参数获取器。
    你的任务是根据当前工具的名称、描述和入参和入参的schema以及运行报错，将当前缺失的参数设置为null，并输出一个JSON格式的字符串。
    ```json
    {
        "host": "请补充主机地址",
        "port": "请补充端口号",
        "username": "请补充用户名",
        "password": "请补充密码"
    }
    ```
    # 样例
    # 工具名称
    mysql_analyzer
    # 工具描述
    分析MySQL数据库性能
    # 工具入参
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # 工具入参schema
   {
        "type": "object",
        "properties": {
                "host": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ],
                    "description": "MySQL数据库的主机地址（可以为字符串或null）"
                },
                "port": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ],
                    "description": "MySQL数据库的端口号（可以是数字、字符串或null）"
                },
                "username": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ],
                    "description": "MySQL数据库的用户名（可以为字符串或null）"
                },
                "password": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ],
                    "description": "MySQL数据库的密码（可以为字符串或null）"
                }
            },
        "required": ["host", "port", "username", "password"]
    }
    # 运行报错
    执行端口扫描命令时，出现了错误：`password is not correct`。
    # 输出
    ```json
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": null,
        "password": null
    }
    ```
    # 工具
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # 工具入参
    {{input_param}}
    # 工具入参schema（部分字段允许为null）
    {{input_schema}}
    # 运行报错
    {{error_message}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a tool parameter getter.
    Your task is to set missing parameters to null based on the current tool's name, description, input parameters, input parameter schema, and runtime errors, and output a JSON-formatted string.
    ```json
    {
        "host": "Please provide the host address",
        "port": "Please provide the port number",
        "username": "Please provide the username",
        "password": "Please provide the password"
    }
    ```
    # Example
    # Tool Name
    mysql_analyzer
    # Tool Description
    Analyze MySQL database performance
    # Tool Input Parameters
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # Tool Input Parameter Schema
    {
        "type": "object",
        "properties": {
            "host": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"}
                ],
                "description": "MySQL database host address (can be a string or null)"
            },
            "port": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"}
                ],
                "description": "MySQL database port number (can be a number, a string, or null)"
            },
            "username": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"}
                ],
                "description": "MySQL database username (can be a string or null)"
            },
            "password": {
                "anyOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ],
                    "description": "MySQL database password (can be a string or null)"
                }
            },
        "required": ["host", "port", "username", "password"]
    }
    # Run error
    When executing the port scan command, an error occurred: `password is not correct`.
    # Output
    ```json
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": null,
        "password": null
    }
    ```
    # Tool
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # Tool input parameters
    {{input_param}}
    # Tool input parameter schema (some fields can be null)
    {{input_schema}}
    # Run error
    {{error_message}}
    # Output
    """
    ),
}

GEN_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个工具参数生成器。
    你的任务是根据总的目标、阶段性的目标、工具信息、工具入参的schema和背景信息生成工具的入参。
    注意：
    1.生成的参数在格式上必须符合工具入参的schema。
    2.总的目标、阶段性的目标和背景信息必须被充分理解，利用其中的信息来生成工具入参。
    3.生成的参数必须符合阶段性目标。

    # 样例
    # 工具信息
    < tool >
    < name > mysql_analyzer < /name >
    < description > 分析MySQL数据库性能 < /description >
    < / tool >
    # 总目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优，ip地址是192.168.1.1，端口是3306，用户名是root，密码是password。
    # 当前阶段目标
    我要连接MySQL数据库，分析性能瓶颈，并调优。
    # 工具入参的schema
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
    # 背景信息
    第1步：生成端口扫描命令
      - 调用工具 `command_generator`，并提供参数 `帮我生成一个mysql端口扫描命令`
      - 执行状态：成功
      - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
    第2步：执行端口扫描命令
        - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
        - 执行状态：成功
        - 得到数据：`{"result": "success"}`
    # 输出
    ```json
    {
        "host": "192.168.1.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    ```
    # 工具
    < tool >
    < name > {{tool_name}} < /name >
    < description > {{tool_description}} < /description >
    < / tool >
    # 总目标
    {{goal}}
    # 当前阶段目标
    {{current_goal}}
    # 工具入参scheme
    {{input_schema}}
    # 背景信息
    {{background_info}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a tool parameter generator.
    Your task is to generate tool input parameters based on the overall goal, phased goals, tool information, tool input parameter schema, and background information.
    Note:
        1. The generated parameters must conform to the tool input parameter schema.
        2. The overall goal, phased goals, and background information must be fully understood and used to generate tool input parameters.
        3. The generated parameters must conform to the phased goals.

    # Example
    # Tool Information
    < tool >
    < name >mysql_analyzer < /name >
    < description > Analyze MySQL Database Performance < /description >
    < / tool >
    # Overall Goal
    I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it. The IP address is 192.168.1.1, the port is 3306, the username is root, and the password is password.
    # Current Phase Goal
    I need to connect to the MySQL database, analyze performance bottlenecks, and optimize it. # Tool input schema
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
    # Background information
    Step 1: Generate a port scan command
        - Call the `command_generator` tool and provide the `Help me generate a MySQL port scan command` parameter
        - Execution status: Success
        - Received data: `{"command": "nmap -sS -p --open 192.168.1.1"}`

    Step 2: Execute the port scan command
        - Call the `command_executor` tool and provide the parameters `{"command": "nmap -sS -p --open 192.168.1.1"}`
        - Execution status: Success
        - Received data: `{"result": "success"}`
    # Output
    ```json
    {
        "host": "192.168.1.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    ```
    # Tool
    < tool >
    < name > {{tool_name}} < /name >
    < description > {{tool_description}} < /description >
    < / tool >
    # Overall goal
    {{goal}}
    # Current stage goal
    {{current_goal}}
    # Tool input scheme
    {{input_schema}}
    # Background information
    {{background_info}}
    # Output
    """
    ),
}

REPAIR_PARAMS: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    你是一个工具参数修复器。
    你的任务是根据当前的工具信息、目标、工具入参的schema、工具当前的入参、工具的报错、补充的参数和补充的参数描述，修复当前工具的入参。
    
    注意：
    1.最终修复的参数要符合目标和工具入参的schema。
    
    # 样例
    # 工具信息
    <tool>
        <name> mysql_analyzer </name>
        <description> 分析MySQL数据库性能 </description>
    </tool>
    # 总目标
    我需要扫描当前mysql数据库，分析性能瓶颈, 并调优
    # 当前阶段目标
    我要连接MySQL数据库，分析性能瓶颈，并调优。
    # 工具入参的schema
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
    # 工具当前的入参
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # 工具的报错
    执行端口扫描命令时，出现了错误：`password is not correct`。
    # 补充的参数
    {
        "username": "admin",
        "password": "admin123"
    }
    # 补充的参数描述
    用户希望使用admin用户和admin123密码来连接MySQL数据库。
    # 输出
    ```json
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "admin",
        "password": "admin123"
    }
    ```
    # 工具
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # 总目标
    {{goal}}
    # 当前阶段目标
    {{current_goal}}
    # 工具入参scheme
    {{input_schema}}
    # 工具入参
    {{input_param}}
    # 运行报错
    {{error_message}}
    # 补充的参数
    {{params}}
    # 补充的参数描述
    {{params_description}}
    # 输出
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    You are a tool parameter fixer.
    Your task is to fix the current tool input parameters based on the current tool information, tool input parameter schema, tool current input parameters, tool error, supplemented parameters, and supplemented parameter descriptions.

    # Example
    # Tool information
    <tool>
        <name> mysql_analyzer </name>
        <description> Analyze MySQL database performance </description>
    </tool>
    # Tool input parameter schema
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
    # Current tool input parameters
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "password"
    }
    # Tool error
    When executing the port scan command, an error occurred: `password is not correct`.
    # Supplementary parameters
    {
        "username": "admin",
        "password": "admin123"
    }
    # Supplementary parameter description
    The user wants to use the admin user and the admin123 password to connect to the MySQL database.
    # Output
    ```json
    {
        "host": "192.0.0.1",
        "port": 3306,
        "username": "admin",
        "password": "admin123"
    }
    ```
    # Tool
    <tool>
        <name> {{tool_name}} </name>
        <description> {{tool_description}} </description>
    </tool>
    # Tool input schema
    {{input_schema}}
    # Tool input parameters
    {{input_param}}
    # Runtime error
    {{error_message}}
    # Supplementary parameters
    {{params}}
    # Supplementary parameter descriptions
    {{params_description}}
    # Output
    """
    ),
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

    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    Comprehensively understand the plan execution results and background information, and report the goal completion status to the user.

    # User Goal

    {{goal}}

    # Plan Execution Status

    To achieve the above goal, you implemented the following plan:

    {{memory}}

    # Additional Background Information:

    {{status}}

    # Now, based on the above information, report the goal completion status to the user:

    """
    ),
}

MEMORY_TEMPLATE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
    {% for ctx in context_list %}
    - 第{{loop.index}}步：{{ctx.step_description}}
        - 调用工具 `{{ctx.step_id}}`，并提供参数 `{{ctx.input_data}}`
        - 执行状态：{{ctx.status}}
        - 得到数据：`{{ctx.output_data}}`
    {% endfor %}
    """
    ),
    LanguageType.ENGLISH: dedent(
        r"""
    {% for ctx in context_list %}
    - Step {{loop.index}}: {{ctx.step_description}}
        - Call the tool `{{ctx.step_id}}` and provide the parameter `{{ctx.input_data}}`
        - Execution status: {{ctx.status}}
        - Receive data: `{{ctx.output_data}}`
    {% endfor %}
    """
    ),
}
