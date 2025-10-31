# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler相关的大模型提示词"""

from apps.models import LanguageType

FLOW_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        ## 任务说明

        根据对话历史和用户查询,从可用选项中选择最匹配的一项。

        ## 示例

        **用户查询:**
        > 使用天气API,查询明天杭州的天气信息

        **可用选项:**
        - **API**:HTTP请求,获取返回的JSON数据
        - **SQL**:查询数据库,获取数据库表中的数据

        **回答:**
        用户明确提到使用天气API,天气数据通常通过外部API获取而非数据库存储,因此选择 API 选项。

        ---

        ## 当前任务

        **用户查询:**
        {{question}}

        **可用选项:**
        {{choice_list}}
    """,
    LanguageType.ENGLISH: r"""
        ## Task Description

        Based on conversation history and user query, select the most matching option from available choices.

        ## Example

        **User Query:**
        > Use the weather API to query the weather information of Hangzhou tomorrow

        **Available Options:**
        - **API**: HTTP request, get the returned JSON data
        - **SQL**: Query the database, get the data in the database table

        **Answer:**
        The user explicitly mentioned using weather API. Weather data is typically accessed via external APIs rather \
than database storage, so the API option is selected.

        ---

        ## Current Task

        **User Query:**
        {{question}}

        **Available Options:**
        {{choice_list}}
    """,
}

FLOW_SELECT_FUNCTION = {
    "name": "select_flow",
    "description": "Select the appropriate flow",
    "parameters": {
        "type": "object",
        "properties": {
            "choice": {
                "type": "string",
                "description": "最匹配用户输入的Flow的名称",
            },
        },
        "required": ["choice"],
    },
}
