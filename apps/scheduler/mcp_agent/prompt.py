# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

MCP_SELECT = dedent(r"""
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

""")
TOOL_SELECT = dedent(r"""
    你是一个乐于助人的智能助手。
    你的任务是：根据当前目标，附加信息，选择最合适的MCP工具。
    ## 选择MCP工具时的注意事项：
    1. 确保充分理解当前目标，选择实现目标所需的MCP工具。
    2. 请在给定的MCP工具列表中选择，不要自己生成MCP工具。
    3. 可以选择一些辅助工具，但必须确保这些工具与当前目标相关。
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
                     )

EVALUATE_GOAL = dedent(r"""
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
        { % for tool in tools % }
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        { % endfor % }
    </tools>

    # 附加信息
    {{additional_info}}

""")
GENERATE_FLOW_NAME = dedent(r"""
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
    扫描MySQL数据库并分析性能瓶颈，进行调优
    # 现在开始生成流程名称：
    # 目标
    {{goal}}
    # 输出
    """)
GET_REPLAN_START_STEP_INDEX = dedent(r"""
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
                "instruction": "生成端口扫描命令：扫描
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
    """)

CREATE_PLAN = dedent(r"""
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
        { % for tool in tools % }
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        { % endfor % }
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
    </thinking> ```json
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
""")
RECREATE_PLAN = dedent(r"""
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
                "content": "执行Result[0]中生成的命令，查看当前机器支持哪些网络扫描工具",
                "tool": "command_executor",
                "instruction": "执行Result[0]中生成的命令"
            },
            {
                "content": "从Result[1]中选择一个网络扫描工具，生成端口扫描命令",
                "tool": "tool_selector",
                "instruction": "选择一个网络扫描工具，生成端口扫描命令"
            },
            {
                "content": "基于result[2]中选择的网络扫描工具，生成端口扫描命令",
                "tool": "command_generator",
                "instruction": "生成端口扫描命令：扫描192.168.1.1的开放端口"
            },
            {
                "content": "在Result[0]的MCP Server上执行Result[3]生成的命令",
                "tool": "command_executor",
                "instruction": "执行端口扫描命令"
            },
            {
                "content": "任务执行完成，端口扫描结果为Result[4]",
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
        { % for tool in tools % }
        - <id> {{tool.id}} </id> <description> {{tool.name}}；{{tool.description}} </description>
        { % endfor % }
    </tools>

    # 当前计划
    {{current_plan}}

    # 运行报错
    {{error_message}}

    # 重新生成的计划
""")
RISK_EVALUATE = dedent(r"""
    你是一个工具执行计划评估器。
    你的任务是根据当前工具的名称、描述和入参以及附加信息，判断当前工具执行的风险并输出提示。
    ```json
    {
        "risk": "low/medium/high",
        "message": "提示信息"
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
        "message": "当前工具将连接到MySQL数据库并分析性能，可能会对数据库性能产生一定影响。请确保在非生产环境中执行此操作。"
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
                       )
# 根据当前计划和报错信息决定下一步执行，具体计划有需要用户补充工具入参、重计划当前步骤、重计划接下来的所有计划
TOOL_EXECUTE_ERROR_TYPE_ANALYSIS = dedent(r"""
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
    {"plans": [
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
    ]}
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
                                          )
# 获取缺失的参数的json结构体
GET_MISSING_PARAMS = dedent(r"""
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
                            )
REPAIR_PARAMS = dedent(r"""
    你是一个工具参数修复器。
    你的任务是根据当前的工具信息、工具入参的schema、工具当前的入参、工具的报错、补充的参数和补充的参数描述，修复当前工具的入参。

    # 样例
    # 工具信息
    <tool>
        <name> mysql_analyzer </name>
        <description> 分析MySQL数据库性能 </description>
    </tool>
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
                       )
FINAL_ANSWER = dedent(r"""
    综合理解计划执行结果和背景信息，向用户报告目标的完成情况。

    # 用户目标

    {{goal}}

    # 计划执行情况

    为了完成上述目标，你实施了以下计划：

    {{memory}}

    # 其他背景信息：

    {{status}}

    # 现在，请根据以上信息，向用户报告目标的完成情况：

""")
MEMORY_TEMPLATE = dedent(r"""
    {% for ctx in context_list % }
    - 第{{loop.index}}步：{{ctx.step_description}}
      - 调用工具 `{{ctx.step_id}}`，并提供参数 `{{ctx.input_data}}`
      - 执行状态：{{ctx.status}}
      - 得到数据：`{{ctx.output_data}}`
    {% endfor % }
""")
