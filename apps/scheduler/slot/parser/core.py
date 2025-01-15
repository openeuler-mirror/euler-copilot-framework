"""参数槽解析器类结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any

from jsonschema import TypeChecker
from jsonschema.protocols import Validator

from apps.entities.enum import SlotType


class SlotParser:
    """参数槽Schema处理器"""

    type: SlotType = SlotType.TYPE
    name: str = ""


    @classmethod
    def convert(cls, data: Any, **kwargs) -> Any:  # noqa: ANN003, ANN401
        """将请求或返回的字段进行处理

        若没有对应逻辑则不实现
        """
        raise NotImplementedError


    @classmethod
    def type_validate(cls, checker: TypeChecker, instance: Any) -> bool:  # noqa: ANN401
        """生成type的验证器

        若没有对应逻辑则不实现
        """
        raise NotImplementedError


    @classmethod
    def format_validate(cls) -> None:
        """生成format的验证器

        若没有对应逻辑则不实现
        """
        raise NotImplementedError


    @classmethod
    def keyword_processor(cls, validator: Validator, keyword_value: Any, instance: Any, schema: dict[str, Any]) -> None:  # noqa: ANN401
        """生成keyword的验证器

        如果没有对应逻辑则不实现
        """
        raise NotImplementedError
