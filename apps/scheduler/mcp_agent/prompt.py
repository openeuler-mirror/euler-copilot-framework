# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.models import LanguageType

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
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            You are an intelligent assistant, your task is to generate a suitable flow name based on the user's goal.

            # Notes when generating flow names:
            1. The flow name should be concise and clear, accurately expressing the process of achieving the \
user's goal.
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
        """,
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
            5.tool_id中的工具ID必须是当前工具集合中存在的工具ID，而不是工具的名称。
            6.工具在<tools></tools> XML标签中给出,工具的id在<tools></tools> 下的<id></id> XML标签中给出。

            # 样例 1
            # 目标
            我需要扫描当前mysql数据库，分析性能瓶颈, 并调优,我的ip是192.168.1.1，数据库端口是3306，\
用户名是root，密码是password
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
                - <id>mcp_tool_1</id> <description>mysql分析工具，用于分析数据库性能/description>
                - <id>mcp_tool_2</id> <description>文件存储工具，用于存储文件</description>
                - <id>mcp_tool_3</id> <description>mongoDB工具，用于操作MongoDB数据库</description>
                - <id>Final</id> <description>结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将作为最终\
结果。</description>
            </tools>
            # 输出
            ```json
            {
                "tool_id": "mcp_tool_1",
                "description": "扫描ip为192.168.1.1的MySQL数据库，端口为3306，用户名为root，密码为password的数据库性能",
            }
            ```
            # 样例二
            # 目标
            计划从杭州到北京的旅游计划
            # 历史记录
            第1步：将杭州转换为经纬度坐标
                - 调用工具 `经纬度工具`，并提供参数 `{"city_from": "杭州", "address": "西湖"}`
                - 执行状态：成功
                - 得到数据：`{"location": "123.456, 78.901"}`
            第2步：查询杭州的天气
                - 调用工具 `天气查询工具`，并提供参数 `{"location": "123.456, 78.901"}`
                - 执行状态：成功
                - 得到数据：`{"weather": "晴", "temperature": "25°C"}`
            第3步：将北京转换为经纬度坐标
                - 调用工具 `经纬度工具`，并提供参数 `{"city_from": "北京", "address": "天安门"}`
                - 执行状态：成功
                - 得到数据：`{"location": "123.456, 78.901"}`
            第4步：查询北京的天气
                - 调用工具 `天气查询工具`，并提供参数 `{"location": "123.456, 78.901"}`
                - 执行状态：成功
                - 得到数据：`{"weather": "晴", "temperature": "25°C"}`
            # 工具
            <tools>
                - <id>mcp_tool_4</id> <description>maps_geo_planner；将详细的结构化地址转换为经纬度坐标。\
支持对地标性名胜景区、建筑物名称解析为经纬度坐标</description>
                - <id>mcp_tool_5</id> <description>weather_query；天气查询，用于查询天气信息</description>
                - <id>mcp_tool_6</id> <description>maps_direction_transit_integrated；根据用户起终点经纬度坐标规划\
综合各类公共（火车、公交、地铁）交通方式的通勤方案，并且返回通勤方案的数据，跨城场景下必须传起点城市与终点城市</description>
                - <id>Final</id> <description>Final；结束步骤，当执行到这一步时，表示计划执行结束，所得到的结果将\
作为最终结果。</description>
            </tools>
            # 输出
            ```json
            {
                "tool_id": "mcp_tool_6",
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
                - <id>{{tool.id}}</id> <description>{{tool.description}}</description>
            {% endfor %}
            </tools>
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a plan generator.
            Please generate a new step based on the user's goal, current plan, and history.

            # A good plan step should:
            1. Use the most appropriate tool for the current step.
            2. Complete the tasks at each stage based on the current plan and history.
            3. Do not select a tool that does not exist.
            4. If you believe the user's goal has been achieved, return to the Final tool to complete the \
plan execution.

            # Example 1
            # Objective
            I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it. My IP \
address is 192.168.1.1, the database port is 3306, my username is root, and my password is password.
            # History
            Step 1: Generate a port scan command
                - Call the `command_generator` tool and provide the `help me generate a MySQL port scan command` \
parameter.
                - Execution status: Success.
                - Result: `{"command": "nmap -sS -p --open 192.168.1.1"}`
            Step 2: Execute the port scan command
                - Call the `command_executor` tool and provide the `{"command": "nmap -sS -p --open 192.168.1.1"}` \
parameter.
                - Execution status: Success.
                - Result: `{"result": "success"}`
            # Tools
            <tools>
                - <id>mcp_tool_1</id> <description>mysql_analyzer; used for analyzing database performance.
                - <id>mcp_tool_2</id> <description>File storage tool; used for storing files.
                - <id>mcp_tool_3</id> <description>MongoDB tool; used for operating MongoDB databases.
                - <id>Final</id> <description>This step completes the plan execution and the result is used as the \
final result. </description>
            </tools>
            # Output
            ```json
            {
                "tool_id": "mcp_tool_1",
                "description": "Scan the database performance of the MySQL database with IP address 192.168.1.1, \
port 3306, username root, and password password",
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
                - <id>mcp_tool_4</id> <description>maps_geo_planner; Converts a detailed structured address \
into longitude and latitude coordinates. Supports parsing landmarks, scenic spots, and building names into \
longitude and latitude coordinates.</description>
                - <id>mcp_tool_5</id> <description>weather_query; Weather query, used to query weather \
information.</description>
                - <id>mcp_tool_6</id> <description>maps_direction_transit_integrated; Plans a commuting plan \
based on the user's starting and ending longitude and latitude coordinates, integrating various public \
transportation modes (train, bus, subway), and returns the commuting plan data. For cross-city scenarios, \
both the starting and ending cities must be provided.</description>
                - <id>Final</id> <description>Final; Final step. When this step is reached, plan execution \
is complete, and the resulting result is used as the final result. </description>
            </tools>
            # Output
            ```json
            {
                "tool_id": "mcp_tool_6",
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
                - <id>{{tool.id}}</id> <description>{{tool.description}}</description>
            {% endfor %}
            </tools>
        """,
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
            ## 工具
            <tool>
                <name>mysql_analyzer</name>
                <description>分析MySQL数据库性能</description>
            </tool>
            ## 工具入参
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }
            ## 附加信息
            1. 当前MySQL数据库的版本是8.0.26
            2. 当前MySQL数据库的配置文件路径是/etc/my.cnf，并含有以下配置项
            ```ini
            [mysqld]
            innodb_buffer_pool_size=1G
            innodb_log_file_size=256M
            ```
            ## 输出
            ```json
            {
                "risk": "中",
                "reason": "当前工具将连接到MySQL数据库并分析性能，可能会对数据库性能产生一定影响。\
请确保在非生产环境中执行此操作。"
            }
            ```

            # 现在开始评估工具执行风险：
            ## 工具
            <tool>
                <name> {{tool_name}} </name>
                <description> {{tool_description}} </description>
            </tool>
            ## 工具入参
            {{input_param}}
            ## 附加信息
            {{additional_info}}
            ## 输出
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a tool execution plan evaluator.
            Your task is to determine the risk of executing the current tool based on its name, description, \
input parameters, and additional information, and output a warning.
            ```json
            {
                "risk": "low/medium/high",
                "reason": "prompt message"
            }
            ```
            # Example
            ## Tool
            <tool>
                <name> mysql_analyzer </name>
                <description> Analyzes MySQL database performance </description>
            </tool>
            ## Tool input
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }
            ## Additional information
            1. The current MySQL database version is 8.0.26
            2. The current MySQL database configuration file path is /etc/my.cnf and contains the following \
configuration items
            ```ini
            [mysqld]
            innodb_buffer_pool_size=1G
            innodb_log_file_size=256M
            ```
            ## Output
            ```json
            {
                "risk": "medium",
                "reason": "This tool will connect to a MySQL database and analyze performance, which may impact \
database performance. This operation should only be performed in a non-production environment."
            }
            ```

            # Now start evaluating the tool execution risk:
            ## Tool
            <tool>
                <name> {{tool_name}} </name>
                <description> {{tool_description}} </description>
            </tool>
            ## Tool Input Parameters
            {{input_param}}
            ## Additional Information
            {{additional_info}}
            ## Output
        """,
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
            ## 用户目标
            我需要扫描当前mysql数据库，分析性能瓶颈, 并调优

            ## 历史
            第1步：生成端口扫描命令
              - 调用工具 `command_generator`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
                - 执行状态：成功
                - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
            第2步：执行端口扫描命令
                - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
                - 执行状态：成功
                - 得到数据：`{"result": "success"}`

            ## 当前步骤
            <step>
                <step_id>step_3</step_id>
                <step_name>mysql_analyzer</step_name>
                <step_instruction>分析MySQL数据库性能</step_instruction>
            </step>

            ## 工具入参
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## 工具运行报错
            执行MySQL性能分析命令时，出现了错误：`host is not correct`。

            ## 输出
            ```json
            {
                "is_param_error": true
            }
            ```

            # 现在开始判断工具执行失败是否是因为参数错误导致的：
            ## 用户目标
            {{goal}}

            ## 历史
            {{history}}

            ## 当前步骤
            <step>
                <step_id> {{step_id}} </step_id>
                <step_name> {{step_name}} </step_name>
                <step_instruction> {{step_instruction}} </step_instruction>
            </step>

            ## 工具入参
            {{input_param}}

            ## 工具运行报错
            {{error_message}}

            ## 输出
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a plan execution expert. Your task is to determine whether the current step execution failure is \
due to parameter errors.
            If so, return `true`; otherwise, return `false`.
            The answer must be in the following format:
            ```json
            {
                "is_param_error": true/false,
            }
            ```

            # Example
            ## User Goal
            I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it.

            ## History
            Step 1: Generate a port scan command
                - Call the `command_generator` tool and provide `{"command": "nmap -sS -p--open 192.168.1.1"}`
                - Execution Status: Success
                - Result: `{"command": "nmap -sS -p--open 192.168.1.1"}`
            Step 2: Execute the port scan command
                - Call the `command_executor` tool and provide `{"command": "nmap -sS -p--open 192.168.1.1"}`
                - Execution Status: Success
                - Result: `{"result": "success"}`

            ## Current step
            <step>
                <step_id>step_3</step_id>
                <step_name>mysql_analyzer</step_name>
                <step_instruction>Analyze MySQL database performance</step_instruction>
            </step>

            ## Tool input parameters
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## Tool execution error
            When executing the MySQL performance analysis command, an error occurred: `host is not correct`.

            ## Output
            ```json
            {
                "is_param_error": true
            }
            ```

            # Now start judging whether the tool execution failure is due to parameter errors:
            ## User goal
            {{goal}}

            ## History
            {{history}}

            ## Current step
            <step>
                <step_id>{{step_id}}</step_id>
                <step_name>{{step_name}}</step_name>
                <step_instruction>{{step_instruction}}</step_instruction>
            </step>

            ## Tool input parameters
            {{input_param}}

            ## Tool error
            {{error_message}}

            ## Output
        """,
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
            ## 工具信息
            <tool>
                <name>port_scanner</name>
                <description>扫描主机端口</description>
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

            ## 工具入参
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## 报错信息
            执行端口扫描命令时，出现了错误：`password is not correct`。

            ## 输出
            扫描端口时发生错误：密码不正确。请检查输入的密码是否正确，并重试。

            # 现在开始转换报错信息：
            ## 工具信息
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
                <input_schema>
                    {{input_schema}}
                </input_schema>
            </tool>

            # 工具入参
            {{input_params}}

            # 报错信息
            {{error_message}}

            ## 输出
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are an intelligent assistant. Your task is to convert the error message generated by the current \
program into a natural language description.
            Please follow the following rules for conversion:
            1. Convert the error message into a natural language description. The description should be concise \
and clear, allowing users to understand the cause and impact of the error.
            2. The description should include the specific content of the error and possible solutions.
            3. The description should avoid using overly technical terms so that users can understand it.
            4. The description should be as brief as possible, within 50 words.
            5. Only output the natural language description, do not output other content.

            # Example
            ## Tool Information
            <tool>
                <name>port_scanner</name>
                <description>Scan host ports</description>
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

            ## Tool input
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## Error message
            An error occurred while executing the port scan command: `password is not correct`.

            ## Output
            An error occurred while scanning the port: The password is incorrect. Please check that the password \
you entered is correct and try again.

            # Now start converting the error message:
            ## Tool information
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
                <input_schema>
                    {{input_schema}}
                </input_schema>
            </tool>

            ## Tool input parameters
            {{input_params}}

            ## Error message
            {{error_message}}

            ## Output
        """,
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
            ## 工具
            <tool>
                <name>mysql_analyzer</name>
                <description>分析MySQL数据库性能</description>
            </tool>

            ## 工具入参
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }

            ## 工具入参schema
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

            #$ 运行报错
            {"err_msg": "执行端口扫描命令时，出现了错误：`password is not correct`。", "data": {} }

            ## 输出
            ```json
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": null,
                "password": null
            }
            ```

            # 现在开始获取缺失的参数：
            ## 工具
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
            </tool>

            ## 工具入参
            {{input_param}}

            ## 工具入参schema（部分字段允许为null）
            {{input_schema}}

            ## 运行报错
            {{error_message}}

            ## 输出
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a tool parameter getter.
            Your task is to set missing parameters to null based on the current tool's name, description, \
input parameters, input parameter schema, and runtime errors, and output a JSON-formatted string.
            ```json
            {
                "host": "Please provide the host address",
                "port": "Please provide the port number",
                "username": "Please provide the username",
                "password": "Please provide the password"
            }
            ```

            # Example
            ## Tool
            <tool>
                <name>mysql_analyzer</name>
                <description>Analyze MySQL database performance</description>
            </tool>

            ## Tool Input Parameters
            ```json
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }
            ```

            ## Tool Input Parameter Schema
            ```json
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

            ## Error info
            {"err_msg": "When executing the port scan command, an error occurred: `password is not correct`.", \
"data": {} }

            ## Output
            ```json
            {
                "host": "192.0.0.1",
                "port": 3306,
                "username": null,
                "password": null
            }
            ```

            # Now start getting the missing parameters:
            ## Tool
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
            </tool>

            ## Tool input parameters
            {{input_param}}

            ## Tool input parameter schema (some fields can be null)
            {{input_schema}}

            ## Error info
            {{error_message}}

            ## Output
        """,
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
            ## 工具信息
            <tool>
                <name>mysql_analyzer</name>
                <description>分析MySQL数据库性能</description>
            </tool>

            ## 总目标
            我需要扫描当前mysql数据库，分析性能瓶颈, 并调优，ip地址是192.168.1.1，端口是3306，用户名是root，\
密码是password。

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

            ## 背景信息
            第1步：生成端口扫描命令
              - 调用工具 `command_generator`，并提供参数 `帮我生成一个mysql端口扫描命令`
              - 执行状态：成功
              - 得到数据：`{"command": "nmap -sS -p--open 192.168.1.1"}`
            第2步：执行端口扫描命令
                - 调用工具 `command_executor`，并提供参数 `{"command": "nmap -sS -p--open 192.168.1.1"}`
                - 执行状态：成功
                - 得到数据：`{"result": "success"}`

            ## 输出
            ```json
            {
                "host": "192.168.1.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }
            ```

            # 现在开始生成工具入参：
            ## 工具
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
            </tool>

            # 总目标
            {{goal}}

            # 当前阶段目标
            {{current_goal}}

            # 工具入参scheme
            {{input_schema}}

            # 背景信息
            {{background_info}}

            # 输出
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a tool parameter generator.
            Your task is to generate tool input parameters based on the overall goal, phased goals, tool information, \
tool input parameter schema, and background information.
            Note:
                1. The generated parameters must conform to the tool input parameter schema.
                2. The overall goal, phased goals, and background information must be fully understood and used to \
generate tool input parameters.
                3. The generated parameters must conform to the phased goals.

            # Example
            ## Tool Information
            <tool>
                <name>mysql_analyzer</name>
                <description>Analyze MySQL Database Performance</description>
            </tool>

            ## Overall Goal
            I need to scan the current MySQL database, analyze performance bottlenecks, and optimize it. The IP \
address is 192.168.1.1, the port is 3306, the username is root, and the password is password.

            ## Current Phase Goal
            I need to connect to the MySQL database, analyze performance bottlenecks, and optimize it.

            ## Tool input schema
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

            ## Background information
            Step 1: Generate a port scan command
                - Call the `command_generator` tool and provide the `Help me generate a MySQL port scan \
command` parameter
                - Execution status: Success
                - Received data: `{"command": "nmap -sS -p --open 192.168.1.1"}`

            Step 2: Execute the port scan command
                - Call the `command_executor` tool and provide the parameters `{"command": "nmap -sS -p --open \
192.168.1.1"}`
                - Execution status: Success
                - Received data: `{"result": "success"}`

            ## Output
            ```json
            {
                "host": "192.168.1.1",
                "port": 3306,
                "username": "root",
                "password": "password"
            }
            ```

            # Now start generating tool input parameters:
            ## Tool
            <tool>
                <name>{{tool_name}}</name>
                <description>{{tool_description}}</description>
            </tool>

            ## Overall goal
            {{goal}}

            ## Current stage goal
            {{current_goal}}

            ## Tool input scheme
            {{input_schema}}

            ## Background information
            {{background_info}}

            ## Output
        """,
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
