"""样例工具 - 主逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

# 可以导入并使用子模块
from .sub_lib import add


class UserCallResult(BaseModel):
    """Call运行后的返回值"""

    message: str = Field(description="Call的文字输出")
    output: Dict[str, Any] = Field(description="Call的结构化数据输出")
    extra: Optional[Dict[str, Any]] = Field(description="Call的额外输出", default=None)


class UserCallParams(BaseModel):
    """此处为工具接受的各项参数。参数可在flow中配置，也可由大模型自动填充"""

    background: str = Field(description="上下文信息，由Executor自动传递")
    question: str = Field(description="给Call提供的用户输入，由Executor自动传递")
    files: list[str] = Field(description="用户询问问题时上传的文件，由Executor自动传递")
    history: list[UserCallResult] = Field(description="Executor中历史Call的返回值，由Executor自动传递")
    task_id: Optional[str] = Field(description="任务ID， 由Executor自动传递")


class UserTool:
    """这是工具类的基础形式"""

    name: str = "user_tool"
    """工具名称，会体现在flow中的on_error.tool和steps[].tool字段内"""
    description: str = "用户自定义工具样例"
    """工具描述，后续将用于自动编排工具"""
    params_obj: UserCallParams
    """工具接受的参数"""
    slot_schema: dict[str, Any]
    """参数槽的JSON Schema"""

    def __init__(self, params: dict[str, Any]):
        """初始化工具，并对参数进行解析。"""
        self._params_obj = UserCallParams(**params)
        pass

    # 工具调用逻辑
    async def call(self, slot_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """工具调用逻辑
        :param slot_data: 参数槽，由大模型交互式填充
        """
        output = {}
        message = ""
        # 返回值为dict类型，其中output字段为工具的原始数据（带格式）；message字段为工具经LLM处理后的数据（仅字符串）；您还可以提供其他数据字段
        return UserCallResult(
            output=output,
            message=message
        )
