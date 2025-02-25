"""Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.scheduler import CallVars


class CoreCall(BaseModel):
    """所有Call的父类，所有Call必须继承此类。"""

    name: ClassVar[str] = Field(description="Call的名称")
    description: ClassVar[str] = Field(description="Call的描述")

    ret_type: ClassVar[type[BaseModel]]

    def __init_subclass__(cls, ret_type: type[BaseModel], **kwargs: Any) -> None:
        """初始化子类"""
        super().__init_subclass__(**kwargs)
        cls.ret_type = ret_type

    class Config:
        """Pydantic 配置类"""

        arbitrary_types_allowed = True


    async def __call__(self, syscall_vars: CallVars, **kwargs: Any) -> type[BaseModel]:
        """Call类实例的调用方法"""
        raise NotImplementedError
