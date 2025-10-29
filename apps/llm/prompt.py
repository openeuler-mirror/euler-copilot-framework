# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""系统提示词模板"""

from textwrap import dedent

from apps.models import LanguageType

JSON_GEN: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个智能助手，可以访问帮助回答用户查询的工具。
            你的任务是使用可用的工具和背景信息来响应查询。

            <instructions>
                - 你可以访问能够帮助收集信息的工具
                - 逐步使用工具，每次使用都基于之前的结果
                - 用户的查询在 <query></query> 标签中提供
                {% if previous_trial %}- 查看 <previous_trial></previous_trial> 信息以避免重复错误{% endif %}
                {% if use_xml_format %}- 使用 XML 样式的标签格式化工具调用，其中工具名称是根标签，每个参数是嵌套标签
                - 使用架构中指定的确切工具名称和参数名称
                - 基本格式结构：
                  <工具名称>
                  <参数名称>值</参数名称>
                  </工具名称>
                - 参数类型：
                  * 字符串：<query>搜索文本</query>
                  * 数字：<limit>10</limit>
                  * 布尔值：<enabled>true</enabled>
                  * 数组（重复标签）：<tag>项目1</tag><tag>项目2</tag>
                  * 对象（嵌套标签）：<config><key>值</key></config>{% endif %}
            </instructions>
            {% if use_xml_format %}

            <example>
                <query>
                    杭州的天气怎么样？
                </query>

                <tools>
                    <descriptions>
                        get_weather: 获取指定城市的当前天气信息
                    </descriptions>
                    <schemas>
                        {
                          "name": "get_weather",
                          "description": "获取指定城市的当前天气信息",
                          "parameters": {
                            "type": "object",
                            "properties": {
                              "city": {
                                "type": "string",
                                "description": "要查询天气的城市名称"
                              },
                              "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "温度单位"
                              },
                              "include_forecast": {
                                "type": "boolean",
                                "description": "是否包含预报数据"
                              }
                            },
                            "required": ["city"]
                          }
                        }
                    </schemas>
                </tools>

                助手响应：
                <get_weather>
                <city>杭州</city>
                <unit>celsius</unit>
                <include_forecast>false</include_forecast>
                </get_weather>
            </example>
            {% endif %}

            <query>
                {{ query }}
            </query>
            {% if previous_trial %}

            <previous_trial>
                <description>
                    你之前的工具调用有不正确的参数。
                </description>
                <arguments>
                    {{ previous_trial }}
                </arguments>
                <error_info>
                    {{ err_info }}
                </error_info>
            </previous_trial>
            {% endif %}

            <tools>
                <descriptions>
                    {{ tool_descriptions }}
                </descriptions>
                <schemas>
                    {{ tool_schemas }}
                </schemas>
            </tools>
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are an intelligent assistant with access to tools that help answer user queries.
            Your task is to respond to queries using the available tools and background information.

            <instructions>
                - You have access to tools that can help gather information
                - Use tools step-by-step, with each use informed by previous results
                - The user's query is provided in the <query></query> tags
                {% if previous_trial %}- Review the <previous_trial></previous_trial> information to avoid \
repeating mistakes{% endif %}
                {% if use_xml_format %}- Format tool calls using XML-style tags where the tool name is the root tag \
and each parameter is a nested tag
                - Use the exact tool name and parameter names as specified in the schema
                - Basic format structure:
                  <tool_name>
                  <param_name>value</param_name>
                  </tool_name>
                - Parameter types:
                  * String: <query>search text</query>
                  * Number: <limit>10</limit>
                  * Boolean: <enabled>true</enabled>
                  * Array (repeat tags): <tag>item1</tag><tag>item2</tag>
                  * Object (nest tags): <config><key>value</key></config>{% endif %}
            </instructions>
            {% if use_xml_format %}

            <example>
                <query>
                    What is the weather like in Hangzhou?
                </query>

                <tools>
                    <descriptions>
                        get_weather: Get current weather information for a specified city
                    </descriptions>
                    <schemas>
                        {
                          "name": "get_weather",
                          "description": "Get current weather information for a specified city",
                          "parameters": {
                            "type": "object",
                            "properties": {
                              "city": {
                                "type": "string",
                                "description": "The city name to query weather for"
                              },
                              "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Temperature unit"
                              },
                              "include_forecast": {
                                "type": "boolean",
                                "description": "Whether to include forecast data"
                              }
                            },
                            "required": ["city"]
                          }
                        }
                    </schemas>
                </tools>

                Assistant response:
                <get_weather>
                <city>Hangzhou</city>
                <unit>celsius</unit>
                <include_forecast>false</include_forecast>
                </get_weather>
            </example>
            {% endif %}

            <query>
                {{ query }}
            </query>
            {% if previous_trial %}

            <previous_trial>
                <description>
                    Your previous tool call had incorrect arguments.
                </description>
                <arguments>
                    {{ previous_trial }}
                </arguments>
                <error_info>
                    {{ err_info }}
                </error_info>
            </previous_trial>
            {% endif %}

            <tools>
                <descriptions>
                    {{ tool_descriptions }}
                </descriptions>
                <schemas>
                    {{ tool_schemas }}
                </schemas>
            </tools>
        """,
    ),
}

