# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""代码执行工具的数据结构"""

from typing import Any

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class CodeInput(DataBase):
    """代码执行工具的输入"""

    code: str = Field(description="要执行的代码")
    code_type: str = Field(description="代码类型，支持python、javascript、bash")
    user_info: dict[str, Any] = Field(description="用户信息", default={})
    security_level: str = Field(description="安全等级，low或high", default="low")
    timeout_seconds: int = Field(description="超时时间（秒）", default=30, ge=1, le=300)
    memory_limit_mb: int = Field(description="内存限制（MB）", default=128, ge=1, le=1024)
    cpu_limit: float = Field(description="CPU限制", default=0.5, ge=0.1, le=2.0)


class CodeOutput(DataBase):
    """代码执行工具的输出"""

    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    result: dict[str, Any] = Field(description="执行结果", default={})
    output: str = Field(description="执行输出", default="")
    error: str = Field(description="错误信息", default="") 