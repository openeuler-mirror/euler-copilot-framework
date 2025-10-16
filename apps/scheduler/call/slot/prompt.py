# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自动参数填充工具的提示词"""
from apps.schemas.enum_var import LanguageType

SLOT_GEN_PROMPT:dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
    <instructions>
        你是一个可以使用工具的AI助手，正尝试使用工具来完成任务。
            目前，你正在生成一个JSON参数对象，以作为调用工具的输入。
            请根据用户输入、背景信息、工具信息和JSON Schema内容，生成符合要求的JSON对象。

            背景信息将在<context>中给出，工具信息将在<tool_info>中给出，JSON Schema将在<tool_call>中给出，\
            用户的问题将在<question>中给出。
            请在<output>中输出生成的JSON对象。

            要求：
            1. 严格按照JSON Schema描述的JSON格式输出，不要编造不存在的字段。
            2. JSON字段的值优先使用用户输入中的内容。如果用户输入没有，则使用背景信息中的内容。
            3. 只输出JSON对象，不要输出任何解释说明，不要输出任何其他内容。
            4. 如果JSON Schema中描述的JSON字段是可选的，则可以不输出该字段。
            5. example中仅为示例，不要照搬example中的内容，不要将example中的内容作为输出。
        </instructions>

        <example>
            <context>
                用户询问杭州今天的天气情况。AI回复杭州今天晴，温度20℃。用户询问杭州明天的天气情况。
            </context>
            <question>
                杭州明天的天气情况如何？
            </question>
            <tool_info>
                工具名称：check_weather
                工具描述：查询指定城市的天气信息
            </tool_info>
            <tool_call>
                {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称"
                        },
                        "date": {
                            "type": "string",
                            "description": "查询日期"
                        },
                        "required": ["city", "date"]
                    }
                }
            </tool_call>
            <tool_output>
                {
                    "city": "杭州",
                    "date": "明天"
                }
            </tool_output>
        </example>

        <context>
            以下是对用户给你的任务的历史总结，在<summary>中给出：
            <summary>
                {{summary}}

                附加的条目化信息：
                {{ facts }}
            </summary>

            在本次任务中，你已经调用过一些工具，并获得了它们的输出，在<tool_data>中给出：
            <tool_data>
                {% for tool in history_data %}
                    <tool>
                        <name>{{ tool.step_name }}</name>
                        <description>{{ tool.step_description }}</description>
                        <output>{{ tool.output_data }}</output>
                    </tool>
                {% endfor %}
            </tool_data>
        </context>
        <question>
            {{question}}
        </question>
        <tool_info>
            工具名称：{{current_tool["name"]}}
            工具描述：{{current_tool["description"]}}
        </tool_info>
        <tool_call>
            {{schema}}
        </tool_call>
        <output>
    """,
    LanguageType.ENGLISH: r"""
    <instructions>
        You are an AI assistant capable of using tools to complete tasks.
            Currently, you are generating a JSON parameter object as input for calling a tool.
            Please generate a compliant JSON object based on user input, background information, tool information, and JSON Schema content.

            Background information will be provided in <context>, tool information in <tool_info>, JSON Schema in <tool_call>, \
            and the user's question in <question>.
            Output the generated JSON object in <output>.

            Requirements:
            1. Strictly follow the JSON format described in the JSON Schema. Do not fabricate non-existent fields.
            2. Prioritize using values from user input for JSON fields. If not available, use content from background information.
            3. Only output the JSON object. Do not include any explanations or additional content.
            4. Optional fields in the JSON Schema may be omitted.
            5. Examples are for illustration only. Do not copy content from examples or use them as output.
            6. Respond in the same language as the user's question by default, unless explicitly requested otherwise.
        </instructions>

        <example>
            <context>
                User asked about today's weather in Hangzhou. AI replied it's sunny, 20℃. User then asks about tomorrow's weather in Hangzhou.
            </context>
            <question>
                What's the weather like in Hangzhou tomorrow?
            </question>
            <tool_info>
                Tool name: check_weather
                Tool description: Query weather information for specified cities
            </tool_info>
            <tool_call>
                {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name"
                        },
                        "date": {
                            "type": "string",
                            "description": "Query date"
                        },
                        "required": ["city", "date"]
                    }
                }
            </tool_call>
            <tool_output>
                {
                    "city": "Hangzhou",
                    "date": "tomorrow"
                }
            </tool_output>
        </example>

        <context>
            Historical summary of tasks given by user, provided in <summary>:
            <summary>
                {{summary}}

                Additional itemized information:
                {{ facts }}
            </summary>

            During this task, you have called some tools and obtained their outputs, provided in <tool_data>:
            <tool_data>
                {% for tool in history_data %}
                    <tool>
                        <name>{{ tool.step_name }}</name>
                        <description>{{ tool.step_description }}</description>
                        <output>{{ tool.output_data }}</output>
                    </tool>
                {% endfor %}
            </tool_data>
        </context>
        <question>
            {{question}}
        </question>
        <tool_info>
            Tool name: {{current_tool["name"]}}
            Tool description: {{current_tool["description"]}}
        </tool_info>
        <tool_call>
            {{schema}}
        </tool_call>
        <output>
    """,
}
