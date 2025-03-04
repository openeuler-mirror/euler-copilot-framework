"""Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from apps.entities.scheduler import CallVars


class CoreCall(BaseModel):
    """所有Call的父类，所有Call必须继承此类。"""

    name: ClassVar[str] = Field(description="Call的名称")
    description: ClassVar[str] = Field(description="Call的描述")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    ret_type: ClassVar[type[BaseModel]]

    def __init_subclass__(cls, ret_type: type[BaseModel], **kwargs: Any) -> None:
        """初始化子类"""
        super().__init_subclass__(**kwargs)
        cls.ret_type = ret_type


    async def init(self, syscall_vars: CallVars, **_kwargs: Any) -> dict[str, Any]:
        """初始化Call类，并返回Call的输入"""
        raise NotImplementedError


    async def exec(self) -> dict[str, Any]:
        """Call类实例的非流式输出方法"""
        raise NotImplementedError


    async def stream(self) -> AsyncGenerator[str, None]:
        """Call类实例的流式输出方法"""
        yield ""
