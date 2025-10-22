# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自动参数填充工具的提示词"""

from textwrap import dedent

from apps.models import LanguageType

# 主查询提示词模板
SLOT_GEN_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
        <instructions>
            <instruction>
                你需要使用 fill_parameters 工具来填充参数。请仔细结合对话上下文，根据用户的问题和历史对话内容，\
为当前工具调用生成合适的参数。要求：
                    1. 严格按照下面提供的 JSON Schema 格式输出，不要编造不存在的字段；
                    2. 参数值优先从用户的当前问题中提取；如果当前问题中没有，则从对话历史中查找相关信息；
                    3. 必须仔细理解对话上下文，确保生成的参数与上下文保持一致，符合用户的真实意图；
                    4. 只输出 JSON 对象，不要包含任何解释说明或其他内容；
                    5. 如果 JSON Schema 中的字段是可选的（optional），在无法确定其值时可以省略该字段；
                    6. 不要编造或猜测参数值，所有参数必须基于对话上下文中的实际信息。
            </instruction>

            <example>
                <context>
                    用户询问："北京今天天气怎么样？" AI回复："北京今天晴，温度20℃。" 用户继续问："明天呢？"
                </context>
                <tool_info>
                    工具名称：check_weather
                    工具描述：查询指定城市的天气信息
                </tool_info>
                <schema>
                    {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称"},
                            "date": {"type": "string", "description": "查询日期"}
                        },
                        "required": ["city", "date"]
                    }
                </schema>
                <output>
                    {
                        "city": "北京",
                        "date": "明天"
                    }
                </output>
            </example>
        </instructions>

        <tool_info>
            工具名称：{{current_tool["name"]}}
            工具描述：{{current_tool["description"]}}
        </tool_info>

        <schema>
            {{schema}}
        </schema>

        现在，请使用 fill_parameters 工具来填充参数：
    """).strip("\n"),
    LanguageType.ENGLISH: dedent(r"""
        <instructions>
            <instruction>
                You need to use the fill_parameters tool to fill in the parameters. Please carefully combine the \
conversation context, and generate appropriate parameters for the current tool call based on the user's question \
and historical conversation. Requirements:
                    1. Strictly follow the JSON Schema format provided below for output; do not fabricate \
non-existent fields;
                    2. Parameter values should be extracted from the user's current question first; if not available \
in the current question, search for relevant information from the conversation history;
                    3. You must carefully understand the conversation context to ensure that the generated parameters \
are consistent with the context and meet the user's true intent;
                    4. Only output the JSON object; do not include any explanations or other content;
                    5. If a field in the JSON Schema is optional, you may omit it when its value cannot be determined;
                    6. Do not fabricate or guess parameter values; all parameters must be based on actual information \
from the conversation context.
            </instruction>

            <example>
                <context>
                    User asks: "What's the weather like in Beijing today?" AI replies: "It's sunny in Beijing today, \
20℃." User continues: "What about tomorrow?"
                </context>
                <tool_info>
                    Tool name: check_weather
                    Tool description: Query weather information for specified cities
                </tool_info>
                <schema>
                    {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"},
                            "date": {"type": "string", "description": "Query date"}
                        },
                        "required": ["city", "date"]
                    }
                </schema>
                <output>
                    {
                        "city": "Beijing",
                        "date": "tomorrow"
                    }
                </output>
            </example>
        </instructions>

        <tool_info>
            Tool name: {{current_tool["name"]}}
            Tool description: {{current_tool["description"]}}
        </tool_info>

        <schema>
            {{schema}}
        </schema>

        Now, please use the fill_parameters tool to fill in the parameters:
    """).strip("\n"),
}

# 任务背景模板（用于conversation中的user消息）
SLOT_SUMMARY_TEMPLATE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
        ## 任务背景

        {{summary}}
        {%- if facts %}

        ### 重要事实信息

        以下是从对话中提取的关键事实，在填充参数时请特别参考这些信息：

        {%- for fact in facts %}
        - {{fact}}
        {%- endfor %}
        {%- endif %}
    """).strip("\n"),
    LanguageType.ENGLISH: dedent(r"""
        ## Task Background

        {{summary}}
        {%- if facts %}

        ### Important Facts

        The following are key facts extracted from the conversation. Please refer to this information when filling \
in parameters:

        {%- for fact in facts %}
        - {{fact}}
        {%- endfor %}
        {%- endif %}
    """).strip("\n"),
}

# 历史工具调用模板（用于conversation中的assistant消息）
SLOT_HISTORY_TEMPLATE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
        ## 历史工具调用记录

        以下是我在处理当前任务时已经调用过的工具及其输出结果，这些信息可能包含了填充参数所需的数据：

        {%- for tool in history_data %}

        ### 工具 {{loop.index}}: {{tool.step_name}}
        {%- if tool.step_description %}

        **功能描述**: {{tool.step_description}}
        {%- endif %}
        {%- if tool.output_data %}

        **输出结果**:
        ```json
        {{tool.output_data | tojson(ensure_ascii=False, indent=2)}}
        ```
        {%- endif %}
        {%- endfor %}
    """).strip("\n"),
    LanguageType.ENGLISH: dedent(r"""
        ## Historical Tool Call Records

        The following are the tools I have already called while processing the current task and their output results. \
This information may contain the data needed to fill in the parameters:

        {%- for tool in history_data %}

        ### Tool {{loop.index}}: {{tool.step_name}}
        {%- if tool.step_description %}

        **Function Description**: {{tool.step_description}}
        {%- endif %}
        {%- if tool.output_data %}

        **Output Result**:
        ```json
        {{tool.output_data | tojson(ensure_ascii=False, indent=2)}}
        ```
        {%- endif %}
        {%- endfor %}
    """).strip("\n"),
}
