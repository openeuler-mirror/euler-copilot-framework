"""Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from pydantic import BaseModel

from apps.entities.scheduler import SysCallVars


class CoreCall(type):
    """Call元类。所有Call必须继承此类，并实现所有方法。"""

    @staticmethod
    def _check_class_attr(cls_name: str, attrs: dict[str, Any]) -> None:
        """检查类属性是否存在"""
        if "name" not in attrs:
            err = f"类{cls_name}中不存在属性name"
            raise AttributeError(err)
        if "description" not in attrs:
            err = f"类{cls_name}中不存在属性description"
            raise AttributeError(err)
        if "__call__" not in attrs or not callable(attrs["__call__"]):
            err = f"类{cls_name}中不存在属性__call__"
            raise AttributeError(err)

    @staticmethod
    def _class_init_fixed(self, syscall_vars: SysCallVars, **kwargs) -> None:  # type: ignore[] # noqa: ANN001, ANN003, PLW0211
        """Call子类的固定初始化函数"""
        self._syscall_vars = syscall_vars
        self._params = self._param_cls.model_validate(kwargs)
        # 调用附加的初始化函数
        self.init(syscall_vars, **kwargs)

    @staticmethod
    def _class_init(self, syscall_vars: SysCallVars, **kwargs) -> None:  # type: ignore[] # noqa: ANN001, ANN003, PLW0211
        """Call子类的附加初始化函数"""


    @staticmethod
    def _class_load(self) -> None:  # type: ignore[] # noqa: ANN001, PLW0211
        """Call子类的文件载入函数"""


    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs) -> type:  # noqa: ANN003
        """创建Call类"""
        # 检查kwargs
        if "param_cls" not in kwargs:
            err = f"请给工具{name}提供参数模板！"
            raise AttributeError(err)
        if not issubclass(kwargs["param_cls"], BaseModel):
            err = f"参数模板{kwargs['param_cls']}不是Pydantic类！"
            raise TypeError(err)
        if "output_cls" not in kwargs:
            err = f"请给工具{name}提供输出模板！"
            raise AttributeError(err)
        if not issubclass(kwargs["output_cls"], BaseModel):
            err = f"输出模板{kwargs['output_cls']}不是Pydantic类！"
            raise TypeError(err)

        # 设置参数相关的属性
        attrs["_param_cls"] = kwargs["param_cls"]
        attrs["params_schema"] = kwargs["param_cls"].model_json_schema()
        attrs["output_schema"] = kwargs["output_cls"].model_json_schema()
        # __init__不允许自定义
        attrs["__init__"] = lambda self, syscall_vars, **kwargs: self._class_init_fixed(syscall_vars, **kwargs)
        # 提供空逻辑占位
        if "init" not in attrs:
            attrs["init"] = cls._class_init
        if "load" not in attrs:
            attrs["load"] = cls._class_load
        # 提供
        return super().__new__(cls, name, bases, attrs)
