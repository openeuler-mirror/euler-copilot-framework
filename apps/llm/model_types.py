# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""模型类型定义和能力规范"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


class ModelType(str, Enum):
    """模型类型枚举"""
    CHAT = "chat"  # 文本对话
    EMBEDDING = "embedding"  # 嵌入
    RERANK = "rerank"  # 重排序
    AUDIO = "audio"  # 语音（预留）
    IMAGE = "image"  # 图像（预留）
    VIDEO = "video"  # 视频（预留）


@dataclass
class ChatCapabilities:
    """文本对话模型能力"""
    # 基础能力
    supports_streaming: bool = True
    supports_function_calling: bool = True
    supports_json_mode: bool = True
    supports_structured_output: bool = False
    
    # 推理能力
    supports_thinking: bool = False
    can_toggle_thinking: bool = False  # 是否支持通过参数开关思维链
    supports_reasoning_content: bool = False  # 是否返回reasoning_content字段
    
    # 参数支持
    max_tokens_param: str = "max_tokens"  # 或 "max_completion_tokens"
    supports_temperature: bool = True
    supports_top_p: bool = True
    supports_top_k: bool = False
    supports_frequency_penalty: bool = False
    supports_presence_penalty: bool = False
    supports_min_p: bool = False  # Qwen3特有
    
    # 高级功能
    supports_response_format: bool = True
    supports_tools: bool = True
    supports_tool_choice: bool = True
    supports_extra_body: bool = True
    supports_stream_options: bool = True
    
    # 特殊参数
    supports_enable_thinking: bool = False  # SiliconFlow/Qwen百炼特有
    supports_thinking_budget: bool = False  # 思维链token预算
    supports_enable_search: bool = False  # 联网搜索


@dataclass
class EmbeddingCapabilities:
    """嵌入模型能力"""
    # 基础能力
    max_input_tokens: int = 512  # 单次输入最大token数
    supports_batch: bool = True  # 是否支持批量输入
    default_dimensions: int = 1024  # 默认向量维度
    
    # 参数支持
    supports_encoding_format: bool = True  # float/base64
    supports_dimensions: bool = False  # 是否支持自定义维度
    available_dimensions: List[int] = field(default_factory=list)  # 可用的维度选项
    
    # 输入类型
    supports_text_input: bool = True
    supports_image_input: bool = False  # 多模态嵌入


@dataclass
class RerankCapabilities:
    """重排序模型能力"""
    # 基础能力
    max_documents: int = 100  # 单次最大文档数
    max_query_length: int = 512  # 查询最大长度
    
    # 参数支持
    supports_top_n: bool = True  # 是否支持返回topN
    supports_return_documents: bool = True  # 是否返回文档内容


@dataclass
class AudioCapabilities:
    """语音模型能力（预留）"""
    supports_tts: bool = False  # 文本转语音
    supports_stt: bool = False  # 语音转文本
    supported_formats: List[str] = field(default_factory=list)  # 支持的音频格式


@dataclass
class ProviderCapabilities:
    """供应商能力配置"""
    provider_name: str
    api_base_url: str
    
    # 认证方式
    auth_type: str = "bearer"  # bearer, api_key, custom
    auth_header: str = "Authorization"
    
    # 各类型模型的默认能力
    chat_capabilities: Optional[ChatCapabilities] = None
    embedding_capabilities: Optional[EmbeddingCapabilities] = None
    rerank_capabilities: Optional[RerankCapabilities] = None
    audio_capabilities: Optional[AudioCapabilities] = None
    
    # 其他配置
    notes: str = ""
    

@dataclass
class ModelConfig:
    """模型配置"""
    provider: str
    model_name: str
    model_type: ModelType
    
    # 模型能力（如果为None，则继承供应商默认配置）
    capabilities: Optional[Any] = None  # ChatCapabilities | EmbeddingCapabilities | RerankCapabilities
    
    # 系列信息（用于能力推断）
    series: Optional[str] = None  # 如 "qwen2.5", "gpt-4", "deepseek-r1"
    
    # 其他元数据
    display_name: Optional[str] = None
    context_window: Optional[int] = None
    notes: str = ""
    
    def get_capabilities(self, provider_capabilities: Optional[ProviderCapabilities] = None) -> Any:
        """获取模型能力（考虑继承）"""
        if self.capabilities:
            return self.capabilities
        
        # 从供应商配置继承
        if provider_capabilities:
            if self.model_type == ModelType.CHAT:
                return provider_capabilities.chat_capabilities
            elif self.model_type == ModelType.EMBEDDING:
                return provider_capabilities.embedding_capabilities
            elif self.model_type == ModelType.RERANK:
                return provider_capabilities.rerank_capabilities
            elif self.model_type == ModelType.AUDIO:
                return provider_capabilities.audio_capabilities
        
        return None

