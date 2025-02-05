"""用于下一步工作流推荐的工具"""
from typing import Any

from apps.scheduler.call.core import CoreCall


class NextFlowCall(metaclass=CoreCall):
    """用于下一步工作流推荐的工具"""

    name = "next_flow"
    description = "用于下一步工作流推荐的工具"

    async def __call__(self, _slot_data: dict[str, Any]):
        """调用NextFlow工具"""
