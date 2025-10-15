# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""系统提示词模板"""

from textwrap import dedent

JSON_GEN_BASIC = dedent(r"""
    Respond to the query according to the background information provided.

    # User query

    User query is given in <query></query> XML tags.

    <query>
    {{ query }}
    </query>

    # Background

    Background information is given in <background></background> XML tags.

    <background>
    Here are the background information between you and the user:

    {% if conversation|length > 0 %}
    {% for message in conversation %}
      <{{ message.role }}>
      {{ message.content }}
      </{{ message.role }}>
    {% endfor %}
    {% else %}
    [No conversation history available.]
    {% endif %}

    {% if previous_trial %}
    You tried to answer the query with one function, but the arguments are incorrect.

    The arguments you provided are:

    ```json
    {{ previous_trial }}
    ```

    And the error information is:

    ```
    {{ err_info }}
    ```
    {% endif %}
    </background>

    # Tools

    You must call one function to assist with the user query.
    Attention: the key in the JSON object is a JSON pointer, which may contain "/", "~" or ".".

    You are provided with function signatures within <tools></tools> XML tags:
    <tools>
    {"type": "function", "function": {"name": "generate", \
"description": "Generate answer based on the background information", "parameters": {{ schema }}}}
    </tools>

    Return a json object with function name and arguments within <tool_call></tool_call> XML tags:
    <tool_call>
    {"name": <function-name>, "arguments": <args-json-object>}
    </tool_call>

    # Output
    <tool_call>
""")
