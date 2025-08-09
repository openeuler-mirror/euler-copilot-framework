# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""记忆提取工具的输入和输出"""

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class DomainGen(BaseModel):
    """生成的领域信息结果"""

    keywords: list[str] = Field(default=[], description="关键词或标签列表，可以为空。")


class FactsGen(BaseModel):
    """生成的提取事实结果"""

    facts: list[str] = Field(default=[], description="从对话中提取的事实条目，可以为空。")


class FactsInput(DataBase):
    """提取事实工具的输入"""

    user_sub: str = Field(description="用户ID")
    message: list[dict[str, str]] = Field(description="消息")


class FactsOutput(DataBase):
    """提取事实工具的输出"""

    facts: list[str] = Field(description="提取的事实")
    domain: list[str] = Field(description="提取的领域")
