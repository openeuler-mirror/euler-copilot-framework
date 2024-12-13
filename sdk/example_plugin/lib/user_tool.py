# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# Python工具基本形式，供用户参考
from __future__ import annotations

from typing import Optional, Any, List, Dict

# 可以使用子模块
from . import sub_lib

from pydantic import BaseModel, Field


# 此处为工具接受的各项参数。参数可在flow中配置，也可由大模型自动填充
class UserCallParams(BaseModel):
    background: str = Field(description="上下文信息，由Executor自动传递")
    question: str = Field(description="给Call提供的用户输入，由Executor自动传递")
    files: List[str] = Field(description="用户询问问题时上传的文件，由Executor自动传递")
    previous_data: Optional[Dict[str, Any]] = Field(description="Flow中前一个Call输出的结构化数据")
    must: str = Field(description="这是必填参数的实例", default="这是默认值的示例")
    opt: Optional[int] = Field(description="这是可选参数的示例")


# 这是工具类的基础形式
class UserTool:
    name: str = "user_tool"  # 工具名称，会体现在flow中的on_error[].tool和steps[].tool字段内
    description: str = "用户自定义工具样例"  # 工具描述，后续将用于自动编排工具
    params_obj: UserCallParams

    def __init__(self, params: Dict[str, Any]):
        # 此处验证传递给Call的参数是否合法
        self.params_obj = UserCallParams(**params)
        pass

    # 此处为工具调用逻辑。注意：函数的参数名称与类型不可改变
    async def call(self, fixed_params: dict) -> Dict[str, Any]:
        # fixed_params：如果用户因为dangerous等原因修改了params，则此处修改params_obj
        self.params_obj = UserCallParams(**fixed_params)

        output = ""
        message = ""
        # 返回值为dict类型，其中output字段为工具的原始数据（带格式）；message字段为工具经LLM处理后的数据（仅字符串）；您还可以提供其他数据字段
        return {
            "output": output,
            "message": message,
        }
