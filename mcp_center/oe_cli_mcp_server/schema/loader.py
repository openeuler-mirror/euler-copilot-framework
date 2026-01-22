from typing import Callable, Optional, List

from pydantic import BaseModel, Field

class Tool(BaseModel):
    """工具函数的结构化模型"""
    # 核心唯一标识（新增）：函数名（全局唯一）
    name: str = Field(description="工具函数名称（全局唯一）")
    # 原有核心字段
    func: Callable = Field(description="可调用的工具函数对象")
    description: str = Field(description="工具函数描述（来自config.json）")
    package: str = Field(description="所属包名")
    # 冗余字段（方便快速查询）
    package_dir: str = Field(description="所属包的目录路径")

    class Config:
        arbitrary_types_allowed = True  # 允许存储Callable类型


class Package(BaseModel):
    """工具包的结构化模型"""
    # 核心唯一标识（新增）：包名（目录名）
    name: str = Field(description="工具包名称（目录名，全局唯一）")
    package_dir: str = Field( description="包的绝对目录路径")
    funcs: List[str] = Field(default_factory=list, description="包内有效工具函数名列表")

