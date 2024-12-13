# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 数据结构定义
from typing import List, Dict, Any, Optional

from pydantic import BaseModel


class ToolData(BaseModel):
    name: str
    params: Dict[str, Any]


class Step(BaseModel):
    name: str
    dangerous: bool = False
    call_type: str
    params: Dict[str, Any] = {}
    next: Optional[str] = None


class Flow(BaseModel):
    on_error: Optional[Step] = Step(
        name="error",
        call_type="llm",
        params={
            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}"
        }
    )
    steps: Dict[str, Step]
    next_flow: Optional[List[str]] = None


class PluginData(BaseModel):
    id: str
    plugin_name: str
    plugin_description: str
    plugin_auth: Optional[dict] = None


class PluginListData(BaseModel):
    code: int
    message: str
    result: list[PluginData]
