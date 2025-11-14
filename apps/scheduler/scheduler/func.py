# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler相关的大模型提示词"""

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
