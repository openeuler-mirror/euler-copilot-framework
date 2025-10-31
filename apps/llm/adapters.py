# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""LLM提供商适配器模块"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelCapabilities:
    """模型能力描述"""
    supports_enable_thinking: bool = False
    supports_reasoning_content: bool = False
    supports_extra_body: bool = True
    supports_stream_options: bool = True
    max_tokens_param: str = "max_completion_tokens"  # 或 "max_tokens"
    
    # 其他可能的能力差异
    supports_function_calling: bool = True
    supports_json_mode: bool = True
    supports_structured_output: bool = False


class LLMProviderAdapter(ABC):
    """LLM提供商适配器基类"""
    
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.capabilities = self._get_model_capabilities()
    
    @abstractmethod
    def _get_model_capabilities(self) -> ModelCapabilities:
        """获取模型能力"""
        pass
    
    def adapt_create_params(self, 
                          base_params: Dict[str, Any], 
                          enable_thinking: bool = False) -> Dict[str, Any]:
        """适配创建参数"""
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
        return enable_thinking and not self.capabilities.supports_enable_thinking


class OpenAIAdapter(LLMProviderAdapter):
    """OpenAI适配器"""
    
    def _get_model_capabilities(self) -> ModelCapabilities:
        # OpenAI的o1系列支持原生thinking
        if "o1" in self.model.lower():
            return ModelCapabilities(
                supports_enable_thinking=True,
                supports_reasoning_content=True,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_completion_tokens"
            )
        else:
            return ModelCapabilities(
                supports_enable_thinking=False,
                supports_reasoning_content=False,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_tokens"
            )


class QwenAdapter(LLMProviderAdapter):
    """阿里百炼Qwen适配器"""
    
    def _get_model_capabilities(self) -> ModelCapabilities:
        # Qwen系列的thinking支持情况
        if any(model_name in self.model.lower() for model_name in ["qwen2.5", "qwen-plus", "qwen-turbo"]):
            return ModelCapabilities(
                supports_enable_thinking=True,
                supports_reasoning_content=True,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_tokens"
            )
        else:
            return ModelCapabilities(
                supports_enable_thinking=False,
                supports_reasoning_content=False,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_tokens"
            )


class SiliconFlowAdapter(LLMProviderAdapter):
    """硅基流动适配器"""
    
    def _get_model_capabilities(self) -> ModelCapabilities:
        # 导入模型注册表
        try:
            from apps.llm.model_registry import get_model_thinking_support
            supports_thinking = get_model_thinking_support(self.provider, self.model)
        except ImportError:
            # 如果无法导入，使用静态配置
            thinking_supported_models = [
                "qwen2.5-coder-32b-instruct",
                "qwen2.5-72b-instruct", 
                "deepseek-v2.5",
            ]
            supports_thinking = any(model in self.model.lower() for model in thinking_supported_models)
        
        return ModelCapabilities(
            supports_enable_thinking=supports_thinking,
            supports_reasoning_content=supports_thinking,
            supports_extra_body=True,
            supports_stream_options=True,
            max_tokens_param="max_tokens"
        )


class DeepSeekAdapter(LLMProviderAdapter):
    """DeepSeek适配器"""
    
    def _get_model_capabilities(self) -> ModelCapabilities:
        # DeepSeek R1系列支持thinking
        if "r1" in self.model.lower():
            return ModelCapabilities(
                supports_enable_thinking=True,
                supports_reasoning_content=True,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_tokens"
            )
        else:
            return ModelCapabilities(
                supports_enable_thinking=False,
                supports_reasoning_content=False,
                supports_extra_body=True,
                supports_stream_options=True,
                max_tokens_param="max_tokens"
            )


class DefaultAdapter(LLMProviderAdapter):
    """默认适配器（保守策略）"""
    
    def _get_model_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_enable_thinking=False,
            supports_reasoning_content=False,
            supports_extra_body=True,
            supports_stream_options=True,
            max_tokens_param="max_tokens"
        )


class AdapterFactory:
    """适配器工厂"""
    
    _adapters = {
        "openai": OpenAIAdapter,
        "qwen": QwenAdapter,
        "siliconflow": SiliconFlowAdapter,
        "deepseek": DeepSeekAdapter,
        "baichuan": DefaultAdapter,
        "spark": DefaultAdapter,
        "wenxin": DefaultAdapter,
        "modelscope": DefaultAdapter,
        "ollama": DefaultAdapter,
        "vllm": DefaultAdapter,
        "mindie": DefaultAdapter,
    }
    
    @classmethod
    def create_adapter(cls, provider: str, model: str) -> LLMProviderAdapter:
        """创建适配器"""
        adapter_class = cls._adapters.get(provider.lower(), DefaultAdapter)
        return adapter_class(provider, model)
    
    @classmethod
    def register_adapter(cls, provider: str, adapter_class: type[LLMProviderAdapter]):
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
