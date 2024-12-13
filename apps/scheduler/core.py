# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# Executor基础类

from abc import ABC, abstractmethod
from typing import Any, List

from pydantic import BaseModel, Field


class ExecutorParameters(BaseModel):
    """
    一个基础的Executor需要接受的参数
    """
    name: str = Field(..., description="Executor的名字")
    question: str = Field(..., description="Executor所需的输入问题")
    context: str = Field(..., description="Executor所需的上下文信息")
    files: List[str] = Field(..., description="适用于该Executor")


class Executor(ABC):
    """
    Executor抽象类，每一个Executor都需要继承此类并实现方法
    """

    # Executor名称
    name: str = ""
    # Executor描述
    description: str = ""

    # Executor保存LLM总结后的上下文，当前Call的原始输出
    context: str = ""
    output: Any = None

    # 用户上传的文件ID
    files: List[str] = []

    @abstractmethod
    def __init__(self, params: ExecutorParameters):
        """
        初始化Executor，并对参数进行解析和处理
        """
        raise NotImplementedError

    @abstractmethod
    async def run(self):
        """
        运行Executor，返回最终结果(message)与最后一个Call的原始输出(output)
        """
        raise NotImplementedError
