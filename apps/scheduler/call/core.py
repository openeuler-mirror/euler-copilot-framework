# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 基础工具类

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import logging


logger = logging.getLogger('gunicorn.error')

class CallParams(BaseModel):
    """
    所有Call都需要接受的参数。包含用户输入、上下文信息、上一个Step的输出等
    """
    background: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    files: Optional[List[str]] = Field(description="用户询问该问题时上传的文件")
    previous_data: Optional[Dict[str, Any]] = Field(description="Executor中上一个工具的结构化数据")
    session_id: Optional[str] = Field(description="用户 user_sub", default="")


class CoreCall(ABC):
    """
    Call抽象类。所有Call必须继承此类，并实现所有方法。
    """

    # 工具名字
    name: str = ""
    # 工具描述
    description: str = ""
    # 工具的参数对象
    params_obj: CallParams

    @abstractmethod
    def __init__(self, params: Dict[str, Any]):
        """
        初始化Call，并对参数进行解析。
        :param params: Call所需的参数。目前由Executor直接填充。后续可以借助LLM能力进行补全。
        """
        # 使用此种方式进行params校验
        self.params_obj = CallParams(**params)
        raise NotImplementedError

    @abstractmethod
    async def call(self, fixed_params: Union[Dict[str, Any], None] = None) -> Dict[str, Any]:
        """
        运行Call。
        :param fixed_params: 经用户修正后的参数。当前未使用，后续用户可对参数动态修改时使用。
        :return: Dict类型的数据。返回值中"output"为工具的原始返回信息（有格式字符串）；"message"为工具经LLM处理后的返回信息（字符串）。也可以带有其他字段，其他字段将起到额外的说明和信息传递作用。
        """
        return {
            "message": "",
            "output": ""
        }
