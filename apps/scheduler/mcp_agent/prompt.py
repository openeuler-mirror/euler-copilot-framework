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

    - 在生成计划之前，请一步一步思考，解析用户的目标，并指导你接下来的生成。\
思考过程应放置在<thinking></thinking> XML标签中。
    - 计划内容中，可以使用"Result[]"来引用之前计划步骤的结果。例如："Result[3]"表示引用第三条计划执行后的结果。
    - 计划不得多于{{ max_num }}条，且每条计划内容应少于150字。

    # 工具

    你可以访问并使用一些工具，这些工具将在<tools></tools> XML标签中给出。

    <tools>
        {% for tool in tools %}
        - <id>{{ tool.id }}</id><description>{{tool.name}}；{{ tool.description }}</description>
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
""")
EVALUATE_PLAN = dedent(r"""
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

""")
FINAL_ANSWER = dedent(r"""
    综合理解计划执行结果和背景信息，向用户报告目标的完成情况。

    # 用户目标

    {{ goal }}

    # 计划执行情况

    为了完成上述目标，你实施了以下计划：

    {{ memory }}

    # 其他背景信息：

    {{ status }}

    # 现在，请根据以上信息，向用户报告目标的完成情况：

""")
MEMORY_TEMPLATE = dedent(r"""
    {% for ctx in context_list %}
    - 第{{ loop.index }}步：{{ ctx.step_description }}
      - 调用工具 `{{ ctx.step_id }}`，并提供参数 `{{ ctx.input_data }}`
      - 执行状态：{{ ctx.status }}
      - 得到数据：`{{ ctx.output_data }}`
    {% endfor %}
""")
