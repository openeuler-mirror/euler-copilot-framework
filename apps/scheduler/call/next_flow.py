"""用于下一步工作流推荐的工具"""
from apps.scheduler.call.core import CallResult, CoreCall


class NextFlowCall(CoreCall):
    """用于下一步工作流推荐的工具"""

    name = "next_flow"
    description = "用于下一步工作流推荐的工具"

    def call(self) -> CallResult:
        return CallResult(output={}, message="", output_schema={})

