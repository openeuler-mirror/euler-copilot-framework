# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的输入输出"""

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class SuggestGenResult(BaseModel):
    """问题推荐结果"""

    predicted_questions: list[str] = Field(description="预测的问题列表")


class SingleFlowSuggestionConfig(BaseModel):
    """涉及单个Flow的问题推荐配置"""

    flow_id: str | None = Field(default=None, description="Flow ID，为None时表示通用问题")
    question: str = Field(default="", description="固定的推荐问题")


class SuggestionInput(DataBase):
    """问题推荐输入"""

    question: str
    user_id: str
    history_questions: list[str]


class SuggestionOutput(DataBase):
    """问题推荐结果"""

    question: str
    flow_name: str | None = Field(default=None, alias="flowName")
    flow_id: str | None = Field(default=None, alias="flowId")
    flow_description: str | None = Field(default=None, alias="flowDescription")
    is_highlight: bool = Field(default=False, alias="isHighlight")
