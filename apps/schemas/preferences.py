# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户偏好设置相关数据结构"""

from pydantic import BaseModel, Field


class ReasoningModelPreference(BaseModel):
    """推理模型偏好设置"""
    
    model_config = {"populate_by_name": True, "protected_namespaces": ()}
    
    llm_id: str = Field(alias="llmId", description="模型ID")
    icon: str = Field(default="", description="模型图标")
    openai_base_url: str = Field(alias="openaiBaseUrl", description="OpenAI API基础URL")
    openai_api_key: str = Field(alias="openaiApiKey", description="OpenAI API密钥")
    model_name: str = Field(alias="modelName", description="模型名称")
    max_tokens: int = Field(alias="maxTokens", description="最大token数")
    is_editable: bool | None = Field(alias="isEditable", default=None, description="是否可编辑")


class EmbeddingModelPreference(BaseModel):
    """嵌入模型偏好设置"""
    
    model_config = {"populate_by_name": True, "protected_namespaces": ()}
    
    llm_id: str = Field(alias="llmId", description="模型ID")
    model_name: str = Field(alias="modelName", description="模型名称")
    icon: str = Field(default="", description="模型图标")
    type: str = Field(description="模型类型")
    endpoint: str = Field(description="API端点")
    api_key: str = Field(alias="apiKey", description="API密钥")


class RerankerModelPreference(BaseModel):
    """重排序模型偏好设置"""
    
    model_config = {"populate_by_name": True, "protected_namespaces": ()}
    
    llm_id: str = Field(alias="llmId", description="模型ID")
    model_name: str = Field(alias="modelName", description="模型名称")
    icon: str = Field(default="", description="模型图标")
    type: str = Field(description="模型类型")
    # 以下字段为可选，因为algorithm类型的reranker可能没有这些字段
    endpoint: str | None = Field(default=None, description="API端点")
    api_key: str | None = Field(alias="apiKey", default=None, description="API密钥")
    name: str | None = Field(default=None, description="算法名称")


class UserPreferences(BaseModel):
    """用户偏好设置"""
    
    model_config = {"populate_by_name": True, "protected_namespaces": ()}

    reasoning_model_preference: ReasoningModelPreference | None = Field(
        default=None, 
        description="推理模型偏好", 
        alias="reasoningModelPreference"
    )
    embedding_model_preference: EmbeddingModelPreference | None = Field(
        default=None, 
        description="嵌入模型偏好", 
        alias="embeddingModelPreference"
    )
    reranker_preference: RerankerModelPreference | None = Field(
        default=None, 
        description="重排序模型偏好", 
        alias="rerankerPreference"
    )
    chain_of_thought_preference: bool = Field(
        default=True, 
        description="思维链偏好", 
        alias="chainOfThoughtPreference"
    )
    auto_execute_preference: bool = Field(
        default=False,
        description="自动执行偏好",
        alias="autoExecutePreference"
    )
