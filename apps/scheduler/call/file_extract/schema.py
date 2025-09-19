# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件提取器Call的Schema定义"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class FileExtractInput(DataBase):
    """文件提取器输入参数"""
    
    parse_method: str = Field(description="文件解析方法")
    target: str = Field(description="目标文件变量引用，格式为{{variable_name}}")


class FileExtractOutput(DataBase):
    """文件提取器输出结果"""
    
    text: str = Field(description="提取的文本内容", default="")
    error: str = Field(description="错误信息", default="")
    report: str = Field(description="详细处理报告", default="")
