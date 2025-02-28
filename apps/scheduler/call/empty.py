"""空Call"""
from typing import Any, ClassVar

from pydantic import BaseModel

from apps.entities.scheduler import CallVars
from apps.scheduler.call.core import CoreCall


class EmptyData(BaseModel):
    """空数据"""


class Empty(CoreCall, ret_type=EmptyData):
    """空Call"""

    name: ClassVar[str] = "空白"
    description: ClassVar[str] = "空白节点，用于占位"


    async def __call__(self, _syscall_vars: CallVars, **_kwargs: Any) -> EmptyData:
        """空Call"""
        return EmptyData()
