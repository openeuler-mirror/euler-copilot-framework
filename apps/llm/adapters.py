# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""LLM提供商适配器模块 V2 - 基于新的模型注册表"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from apps.llm.model_types import ModelType, ChatCapabilities

logger = logging.getLogger(__name__)


class LLMProviderAdapterV2(ABC):
    """LLM提供商适配器基类 V2"""
    
    def __init__(self, provider: str, model: str, capabilities: Optional[ChatCapabilities] = None):
        self.provider = provider
        self.model = model
        self.capabilities = capabilities or self._get_default_capabilities()
    
    @abstractmethod
    def _get_default_capabilities(self) -> ChatCapabilities:
        """获取默认能力（当注册表中没有配置时）"""
        pass
    
    def adapt_create_params(self, 
                          base_params: Dict[str, Any], 
                          enable_thinking: bool = False) -> Dict[str, Any]:
        """适配创建参数"""
        if not self.capabilities:
            return base_params
        
        adapted_params = base_params.copy()
        
        # 处理思维链参数
        if enable_thinking:
            if self.capabilities.supports_enable_thinking:
                # 使用原生enable_thinking支持
                if "extra_body" not in adapted_params:
                    adapted_params["extra_body"] = {}
                adapted_params["extra_body"]["enable_thinking"] = True
                logger.info(f"[{self.provider}] 使用原生enable_thinking支持")
            else:
                # 移除不支持的参数，使用prompt方式
                if "extra_body" in adapted_params:
                    adapted_params["extra_body"].pop("enable_thinking", None)
                    if not adapted_params["extra_body"]:
                        del adapted_params["extra_body"]
                logger.info(f"[{self.provider}] 模型不支持enable_thinking，将使用prompt方式")
        else:
            # 不启用思维链时，确保参数正确
            if "extra_body" in adapted_params:
                adapted_params["extra_body"].pop("enable_thinking", None)
                if not adapted_params["extra_body"]:
                    del adapted_params["extra_body"]
        
        # 处理temperature参数
        if not self.capabilities.supports_temperature and "temperature" in adapted_params:
            logger.warning(f"[{self.provider}] 模型不支持temperature参数，已移除")
            del adapted_params["temperature"]
        
        # 处理 extra_body 中的参数过滤
        if "extra_body" in adapted_params:
            extra_body = adapted_params["extra_body"]
            
            # 处理 frequency_penalty
            if not self.capabilities.supports_frequency_penalty and "frequency_penalty" in extra_body:
                logger.warning(f"[{self.provider}] 模型不支持frequency_penalty参数，已从extra_body移除")
                del extra_body["frequency_penalty"]
            
            # 处理 presence_penalty
            if not self.capabilities.supports_presence_penalty and "presence_penalty" in extra_body:
                logger.warning(f"[{self.provider}] 模型不支持presence_penalty参数，已从extra_body移除")
                del extra_body["presence_penalty"]
            
            # 处理 min_p
            if not self.capabilities.supports_min_p and "min_p" in extra_body:
                logger.warning(f"[{self.provider}] 模型不支持min_p参数，已从extra_body移除")
                del extra_body["min_p"]
            
            # 处理 top_k
            if not self.capabilities.supports_top_k and "top_k" in extra_body:
                logger.warning(f"[{self.provider}] 模型不支持top_k参数，已从extra_body移除")
                del extra_body["top_k"]
            
            # 如果 extra_body 为空，删除它
            if not extra_body:
                del adapted_params["extra_body"]
        
        # 处理top_p参数（顶级参数）
        if not self.capabilities.supports_top_p and "top_p" in adapted_params:
            logger.warning(f"[{self.provider}] 模型不支持top_p参数，已移除")
            del adapted_params["top_p"]
        
        # 处理其他参数适配
        if not self.capabilities.supports_extra_body and "extra_body" in adapted_params:
            logger.warning(f"[{self.provider}] 模型不支持extra_body参数，已移除")
            del adapted_params["extra_body"]
        
        if not self.capabilities.supports_stream_options and "stream_options" in adapted_params:
            logger.warning(f"[{self.provider}] 模型不支持stream_options参数，已移除")
            del adapted_params["stream_options"]
        
        # 适配max_tokens参数名
        if "max_completion_tokens" in adapted_params and self.capabilities.max_tokens_param == "max_tokens":
            adapted_params["max_tokens"] = adapted_params.pop("max_completion_tokens")
        elif "max_tokens" in adapted_params and self.capabilities.max_tokens_param == "max_completion_tokens":
            adapted_params["max_completion_tokens"] = adapted_params.pop("max_tokens")
        
        return adapted_params
    
    def should_use_prompt_thinking(self, enable_thinking: bool) -> bool:
        """判断是否应该使用prompt方式的思维链"""
        if not self.capabilities:
            return False
        return enable_thinking and not self.capabilities.supports_enable_thinking


class OpenAIAdapterV2(LLMProviderAdapterV2):
    """OpenAI适配器 V2"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        # OpenAI的o1系列支持原生thinking
        if "o1" in self.model.lower():
            return ChatCapabilities(
                supports_thinking=True,
                can_toggle_thinking=True,
                supports_enable_thinking=True,
                supports_reasoning_content=True,
                max_tokens_param="max_completion_tokens"
            )
        else:
            return ChatCapabilities(
                supports_thinking=False,
                max_tokens_param="max_tokens"
            )


class QwenAdapterV2(LLMProviderAdapterV2):
    """阿里百炼Qwen适配器 V2"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        # Qwen系列的thinking支持情况
        if any(model_name in self.model.lower() for model_name in ["qwen2.5", "qwen-plus", "qwen-turbo"]):
            return ChatCapabilities(
                supports_thinking=True,
                can_toggle_thinking=True,
                supports_enable_thinking=True,
                supports_reasoning_content=True,
                supports_enable_search=True
            )
        else:
            return ChatCapabilities(
                supports_enable_search=True
            )


class SiliconFlowAdapterV2(LLMProviderAdapterV2):
    """硅基流动适配器 V2"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        # 使用模型注册表获取能力
        try:
            from apps.llm.model_registry import global_model_registry_v2
            capabilities = global_model_registry_v2.get_model_capabilities(
                self.provider, self.model, ModelType.CHAT
            )
            if capabilities and isinstance(capabilities, ChatCapabilities):
                return capabilities
        except Exception as e:
            logger.warning(f"无法从注册表获取能力: {e}")
        
        # 默认能力
        return ChatCapabilities()


class DeepSeekAdapterV2(LLMProviderAdapterV2):
    """DeepSeek适配器 V2"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        # DeepSeek R1系列支持thinking
        if "r1" in self.model.lower() or "reasoner" in self.model.lower():
            return ChatCapabilities(
                supports_thinking=True,
                can_toggle_thinking=False,  # 不支持关闭思维链
                supports_reasoning_content=True
            )
        else:
            return ChatCapabilities()


class BaichuanAdapterV2(LLMProviderAdapterV2):
    """百川智能适配器 V2"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        return ChatCapabilities(
            supports_extra_body=False,
            supports_stream_options=False,
            supports_response_format=False,
            supports_enable_search=True
        )


class DefaultAdapterV2(LLMProviderAdapterV2):
    """默认适配器 V2（保守策略）"""
    
    def _get_default_capabilities(self) -> ChatCapabilities:
        return ChatCapabilities()


class AdapterFactoryV2:
    """适配器工厂 V2"""
    
    _adapters = {
        "openai": OpenAIAdapterV2,
        "qwen": QwenAdapterV2,
        "siliconflow": SiliconFlowAdapterV2,
        "deepseek": DeepSeekAdapterV2,
        "baichuan": BaichuanAdapterV2,
        "spark": DefaultAdapterV2,
        "wenxin": DefaultAdapterV2,
        "modelscope": DefaultAdapterV2,
        "ollama": DefaultAdapterV2,
        "vllm": DefaultAdapterV2,
        "mindie": DefaultAdapterV2,
    }
    
    @classmethod
    def create_adapter(cls, provider: str, model: str, capabilities: Optional[ChatCapabilities] = None) -> LLMProviderAdapterV2:
        """创建适配器
        
        Args:
            provider: 供应商名称
            model: 模型名称
            capabilities: 模型能力（可选，如果提供则使用，否则使用默认）
        """
        adapter_class = cls._adapters.get(provider.lower(), DefaultAdapterV2)
        return adapter_class(provider, model, capabilities)
    
    @classmethod
    def create_adapter_from_registry(cls, provider: str, model: str) -> LLMProviderAdapterV2:
        """从注册表创建适配器"""
        try:
            from apps.llm.model_registry import global_model_registry_v2
            capabilities = global_model_registry_v2.get_model_capabilities(
                provider, model, ModelType.CHAT
            )
            if capabilities and isinstance(capabilities, ChatCapabilities):
                return cls.create_adapter(provider, model, capabilities)
        except Exception as e:
            logger.warning(f"无法从注册表创建适配器: {e}")
        
        # 回退到默认创建方式
        return cls.create_adapter(provider, model)
    
    @classmethod
    def register_adapter(cls, provider: str, adapter_class: type[LLMProviderAdapterV2]):
        """注册新的适配器"""
        cls._adapters[provider.lower()] = adapter_class


def get_provider_from_endpoint(endpoint: str) -> str:
    """从endpoint推断provider"""
    if not endpoint:
        return "unknown"
    
    endpoint_lower = endpoint.lower()
    
    if "openai.com" in endpoint_lower:
        return "openai"
    elif "siliconflow.cn" in endpoint_lower:
        return "siliconflow"
    elif "dashscope.aliyuncs.com" in endpoint_lower:
        return "qwen"
    elif "api.deepseek.com" in endpoint_lower:
        return "deepseek"
    elif "baichuan-ai.com" in endpoint_lower:
        return "baichuan"
    elif "spark-api" in endpoint_lower:
        return "spark"
    elif "qianfan.baidubce.com" in endpoint_lower:
        return "wenxin"
    else:
        return "unknown"


# 兼容旧的导入
LLMProviderAdapter = LLMProviderAdapterV2
AdapterFactory = AdapterFactoryV2

