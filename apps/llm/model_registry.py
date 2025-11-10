# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""模型注册表和配置管理 V2 - 支持多级继承和模型类型分离"""

import logging
import json
import copy
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from apps.llm.model_types import (
    ModelType,
    ChatCapabilities,
    EmbeddingCapabilities,
    RerankCapabilities,
    AudioCapabilities,
    ProviderCapabilities,
    ModelConfig
)

logger = logging.getLogger(__name__)


class ModelRegistryV2:
    """模型注册表 V2 - 支持供应商能力继承"""
    
    def __init__(self, providers_config_path: Optional[str] = None, models_config_path: Optional[str] = None):
        self._providers: Dict[str, ProviderCapabilities] = {}
        self._models: Dict[str, ModelConfig] = {}
        
        # 加载配置
        if providers_config_path:
            self.load_providers_from_file(providers_config_path)
        if models_config_path:
            self.load_models_from_file(models_config_path)
    
    def register_provider(self, provider_config: Dict[str, Any]):
        """注册供应商配置"""
        provider_name = provider_config["provider_name"]
        
        # 解析各类型模型能力
        chat_caps = None
        if "chat_capabilities" in provider_config:
            chat_caps = ChatCapabilities(**provider_config["chat_capabilities"])
        
        embedding_caps = None
        if "embedding_capabilities" in provider_config:
            embedding_caps = EmbeddingCapabilities(**provider_config["embedding_capabilities"])
        
        rerank_caps = None
        if "rerank_capabilities" in provider_config:
            rerank_caps = RerankCapabilities(**provider_config["rerank_capabilities"])
        
        audio_caps = None
        if "audio_capabilities" in provider_config:
            audio_caps = AudioCapabilities(**provider_config["audio_capabilities"])
        
        # 创建供应商配置对象
        provider = ProviderCapabilities(
            provider_name=provider_name,
            api_base_url=provider_config.get("api_base_url", ""),
            auth_type=provider_config.get("auth_type", "bearer"),
            auth_header=provider_config.get("auth_header", "Authorization"),
            chat_capabilities=chat_caps,
            embedding_capabilities=embedding_caps,
            rerank_capabilities=rerank_caps,
            audio_capabilities=audio_caps,
            notes=provider_config.get("notes", "")
        )
        
        self._providers[provider_name] = provider
        logger.info(f"注册供应商: {provider_name}")
    
    def register_model(self, model_config: Dict[str, Any]):
        """注册模型配置"""
        provider = model_config["provider"]
        model_name = model_config["model_name"]
        key = f"{provider}:{model_name}"
        
        # 解析模型类型
        model_type = ModelType(model_config["model_type"])
        
        # 解析能力配置（支持继承）
        capabilities = None
        if "capabilities" in model_config:
            caps_config = model_config["capabilities"]
            
            # 处理继承
            if isinstance(caps_config, dict) and "_inherit" in caps_config:
                inherit_from = caps_config["_inherit"]  # 格式: "siliconflow.chat_capabilities"
                capabilities = self._inherit_capabilities(inherit_from, caps_config, model_type)
            else:
                # 直接创建能力对象
                capabilities = self._create_capabilities(model_type, caps_config)
        
        # 创建模型配置对象
        model = ModelConfig(
            provider=provider,
            model_name=model_name,
            model_type=model_type,
            capabilities=capabilities,
            series=model_config.get("series"),
            display_name=model_config.get("display_name"),
            context_window=model_config.get("context_window"),
            notes=model_config.get("notes", "")
        )
        
        self._models[key] = model
        logger.debug(f"注册模型: {key}")
    
    def _inherit_capabilities(self, inherit_from: str, override_config: Dict[str, Any], model_type: ModelType) -> Any:
        """从供应商配置继承能力"""
        # 解析继承路径: "siliconflow.chat_capabilities"
        parts = inherit_from.split(".")
        if len(parts) != 2:
            logger.warning(f"无效的继承路径: {inherit_from}")
            return None
        
        provider_name, capability_name = parts
        provider = self._providers.get(provider_name)
        if not provider:
            logger.warning(f"未找到供应商: {provider_name}")
            return None
        
        # 获取基础能力
        base_capabilities = None
        if capability_name == "chat_capabilities" and provider.chat_capabilities:
            base_capabilities = asdict(provider.chat_capabilities)
        elif capability_name == "embedding_capabilities" and provider.embedding_capabilities:
            base_capabilities = asdict(provider.embedding_capabilities)
        elif capability_name == "rerank_capabilities" and provider.rerank_capabilities:
            base_capabilities = asdict(provider.rerank_capabilities)
        elif capability_name == "audio_capabilities" and provider.audio_capabilities:
            base_capabilities = asdict(provider.audio_capabilities)
        
        if not base_capabilities:
            logger.warning(f"未找到能力配置: {inherit_from}")
            return None
        
        # 合并覆盖配置
        merged_config = copy.deepcopy(base_capabilities)
        for key, value in override_config.items():
            if key != "_inherit":
                merged_config[key] = value
        
        # 创建能力对象
        return self._create_capabilities(model_type, merged_config)
    
    def _create_capabilities(self, model_type: ModelType, config: Dict[str, Any]) -> Any:
        """创建能力对象"""
        try:
            if model_type == ModelType.CHAT:
                return ChatCapabilities(**config)
            elif model_type == ModelType.EMBEDDING:
                return EmbeddingCapabilities(**config)
            elif model_type == ModelType.RERANK:
                return RerankCapabilities(**config)
            elif model_type == ModelType.AUDIO:
                return AudioCapabilities(**config)
        except Exception as e:
            logger.error(f"创建能力对象失败: {e}")
            return None
    
    def get_model_config(self, provider: str, model_name: str) -> Optional[ModelConfig]:
        """获取模型配置，支持智能推断"""
        key = f"{provider}:{model_name}"
        
        # 1. 直接匹配
        if key in self._models:
            return self._models[key]
        
        # 2. 相同模型名不同供应商的能力匹配
        model_config = self._find_by_model_name(model_name)
        if model_config:
            logger.debug(f"通过模型名匹配找到配置: {provider}:{model_name} -> {model_config.provider}:{model_config.model_name}")
            # 返回一个新的配置，使用当前provider但保留原有能力
            return ModelConfig(
                provider=provider,
                model_name=model_name,
                model_type=model_config.model_type,
                capabilities=model_config.capabilities,
                series=model_config.series,
                display_name=model_config.display_name,
                context_window=model_config.context_window,
                notes=f"基于{model_config.provider}:{model_config.model_name}推断"
            )
        
        # 3. 系列推断逻辑
        model_config = self._infer_by_series(provider, model_name)
        if model_config:
            logger.debug(f"通过系列推断找到配置: {provider}:{model_name}")
            return model_config
        
        return None
    
    def _find_by_model_name(self, model_name: str) -> Optional[ModelConfig]:
        """通过模型名查找相同模型的配置信息"""
        for model_config in self._models.values():
            if model_config.model_name == model_name:
                return model_config
        return None
    
    def _infer_by_series(self, provider: str, model_name: str) -> Optional[ModelConfig]:
        """通过系列推断模型配置"""
        model_lower = model_name.lower()
        
        # 定义系列匹配规则
        series_rules = [
            # OpenAI系列
            {
                "patterns": ["gpt-4", "gpt4"],
                "reference_models": ["gpt-4o", "gpt-4o-mini"],
                "series_name": "GPT-4"
            },
            {
                "patterns": ["o1"],
                "reference_models": ["o1-preview", "o1-mini"],
                "series_name": "O1"
            },
            # Qwen系列
            {
                "patterns": ["qwen2.5", "qwen-2.5"],
                "reference_models": ["qwen2.5-72b-instruct", "Qwen/Qwen2.5-72B-Instruct"],
                "series_name": "Qwen2.5"
            },
            {
                "patterns": ["qwen3", "qwen-3"],
                "reference_models": ["Qwen/Qwen3-8B", "qwen2.5-72b-instruct"],
                "series_name": "Qwen3"
            },
            {
                "patterns": ["qwen-plus", "qwen-turbo", "qwen-max"],
                "reference_models": ["qwen-plus", "qwen-turbo"],
                "series_name": "Qwen-API"
            },
            # DeepSeek系列
            {
                "patterns": ["deepseek-r1", "deepseek-reasoner"],
                "reference_models": ["deepseek-r1", "deepseek-reasoner"],
                "series_name": "DeepSeek-R"
            },
            {
                "patterns": ["deepseek-v2", "deepseek-v3"],
                "reference_models": ["deepseek-ai/DeepSeek-V2.5"],
                "series_name": "DeepSeek-V"
            },
            {
                "patterns": ["deepseek-chat"],
                "reference_models": ["deepseek-chat"],
                "series_name": "DeepSeek"
            },
            # Yi系列
            {
                "patterns": ["yi-lightning", "yi-large"],
                "reference_models": ["01-ai/Yi-Lightning"],
                "series_name": "Yi"
            },
            # GLM系列
            {
                "patterns": ["glm-4", "glm4"],
                "reference_models": ["THUDM/glm-4-9b-chat", "glm-4-plus"],
                "series_name": "GLM-4"
            },
            # Baichuan系列
            {
                "patterns": ["baichuan2", "baichuan-2"],
                "reference_models": ["Baichuan2-Turbo"],
                "series_name": "Baichuan2"
            },
            {
                "patterns": ["baichuan3", "baichuan-3"],
                "reference_models": ["Baichuan3-Turbo"],
                "series_name": "Baichuan3"
            },
            # Kimi系列
            {
                "patterns": ["moonshot", "kimi"],
                "reference_models": ["moonshot-v1-32k"],
                "series_name": "Kimi"
            },
            # ERNIE系列
            {
                "patterns": ["ernie-4", "ernie4"],
                "reference_models": ["ernie-4.0-turbo-8k"],
                "series_name": "ERNIE-4"
            },
        ]
        
        # 查找匹配的系列
        for rule in series_rules:
            for pattern in rule["patterns"]:
                if pattern in model_lower:
                    # 找到匹配的系列，使用参考模型的能力
                    for ref_model in rule["reference_models"]:
                        ref_config = self._find_by_model_name(ref_model)
                        if ref_config:
                            logger.debug(f"系列推断: {model_name} 匹配 {rule['series_name']} 系列，参考模型: {ref_model}")
                            # 创建新的ModelConfig，保持原有provider和model_name
                            return ModelConfig(
                                provider=provider,
                                model_name=model_name,
                                model_type=ref_config.model_type,
                                capabilities=ref_config.capabilities,
                                series=ref_config.series,
                                display_name=model_name,
                                context_window=ref_config.context_window,
                                notes=f"基于{rule['series_name']}系列推断，参考模型: {ref_model}"
                            )
        
        return None
    
    def get_model_capabilities(self, provider: str, model_name: str, model_type: ModelType = ModelType.CHAT) -> Optional[Any]:
        """获取模型能力"""
        model_config = self.get_model_config(provider, model_name)
        if model_config:
            return model_config.get_capabilities(self._providers.get(provider))
        
        # 如果没有找到模型配置，尝试返回供应商默认能力
        provider_config = self._providers.get(provider)
        if provider_config:
            if model_type == ModelType.CHAT:
                return provider_config.chat_capabilities
            elif model_type == ModelType.EMBEDDING:
                return provider_config.embedding_capabilities
            elif model_type == ModelType.RERANK:
                return provider_config.rerank_capabilities
            elif model_type == ModelType.AUDIO:
                return provider_config.audio_capabilities
        
        return None
    
    def get_provider_config(self, provider: str) -> Optional[ProviderCapabilities]:
        """获取供应商配置"""
        return self._providers.get(provider)
    
    def list_models_by_provider(self, provider: str, model_type: Optional[ModelType] = None) -> List[ModelConfig]:
        """按供应商列出模型"""
        models = [model for model in self._models.values() if model.provider == provider]
        if model_type:
            models = [model for model in models if model.model_type == model_type]
        return models
    
    def list_models_by_type(self, model_type: ModelType) -> List[ModelConfig]:
        """按类型列出模型"""
        return [model for model in self._models.values() if model.model_type == model_type]
    
    def load_providers_from_file(self, filepath: str):
        """从文件加载供应商配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if "providers" in config:
                for provider_name, provider_config in config["providers"].items():
                    self.register_provider(provider_config)
                logger.info(f"从 {filepath} 加载了 {len(config['providers'])} 个供应商配置")
        except FileNotFoundError:
            logger.warning(f"供应商配置文件不存在: {filepath}")
        except Exception as e:
            logger.error(f"加载供应商配置失败: {e}")
    
    def load_models_from_file(self, filepath: str):
        """从文件加载模型配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if "models" in config:
                for key, model_config in config["models"].items():
                    # 跳过注释键
                    if key.startswith("_comment"):
                        continue
                    self.register_model(model_config)
                logger.info(f"从 {filepath} 加载了模型配置")
        except FileNotFoundError:
            logger.warning(f"模型配置文件不存在: {filepath}")
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "providers": {
                name: {
                    "provider_name": p.provider_name,
                    "api_base_url": p.api_base_url,
                    "auth_type": p.auth_type,
                    "auth_header": p.auth_header,
                    "chat_capabilities": asdict(p.chat_capabilities) if p.chat_capabilities else None,
                    "embedding_capabilities": asdict(p.embedding_capabilities) if p.embedding_capabilities else None,
                    "rerank_capabilities": asdict(p.rerank_capabilities) if p.rerank_capabilities else None,
                    "audio_capabilities": asdict(p.audio_capabilities) if p.audio_capabilities else None,
                    "notes": p.notes
                }
                for name, p in self._providers.items()
            },
            "models": {
                f"{m.provider}:{m.model_name}": {
                    "provider": m.provider,
                    "model_name": m.model_name,
                    "model_type": m.model_type.value,
                    "series": m.series,
                    "display_name": m.display_name,
                    "context_window": m.context_window,
                    "capabilities": asdict(m.capabilities) if m.capabilities else None,
                    "notes": m.notes
                }
                for m in self._models.values()
            },
            "version": "2.0"
        }
    
    def get_model_info(self, provider: str, model_name: str) -> Optional['ModelInfo']:
        """
        获取模型信息（兼容旧版API）
        
        该方法用于兼容旧代码，返回一个类似旧版ModelInfo的对象
        
        :param provider: 供应商名称
        :param model_name: 模型名称
        :return: ModelInfo对象（兼容格式）或None
        """
        from dataclasses import dataclass
        
        # 定义兼容的ModelInfo类
        @dataclass
        class ModelInfo:
            """模型信息（兼容格式）"""
            provider: str
            model_name: str
            supports_thinking: bool = False
            can_toggle_thinking: bool = False
            supports_function_calling: bool = True
            supports_json_mode: bool = True
            supports_structured_output: bool = False
            max_tokens_param: str = "max_tokens"
            notes: str = ""
        
        # 从V2注册表获取配置
        model_config = self.get_model_config(provider, model_name)
        
        if not model_config:
            # 如果没有找到模型配置，尝试返回供应商默认能力
            provider_config = self._providers.get(provider)
            if provider_config and provider_config.chat_capabilities:
                caps = provider_config.chat_capabilities
                return ModelInfo(
                    provider=provider,
                    model_name=model_name,
                    supports_thinking=caps.supports_thinking,
                    can_toggle_thinking=caps.can_toggle_thinking,
                    supports_function_calling=caps.supports_function_calling,
                    supports_json_mode=caps.supports_json_mode,
                    supports_structured_output=caps.supports_structured_output,
                    max_tokens_param=caps.max_tokens_param,
                    notes=provider_config.notes
                )
            return None
        
        # 获取chat能力（如果有的话）
        capabilities = model_config.get_capabilities(self._providers.get(provider))
        
        if capabilities and isinstance(capabilities, ChatCapabilities):
            return ModelInfo(
                provider=model_config.provider,
                model_name=model_config.model_name,
                supports_thinking=capabilities.supports_thinking,
                can_toggle_thinking=capabilities.can_toggle_thinking,
                supports_function_calling=capabilities.supports_function_calling,
                supports_json_mode=capabilities.supports_json_mode,
                supports_structured_output=capabilities.supports_structured_output,
                max_tokens_param=capabilities.max_tokens_param,
                notes=model_config.notes
            )
        
        # 如果模型不是chat类型或没有能力信息，返回基本信息
        return ModelInfo(
            provider=model_config.provider,
            model_name=model_config.model_name,
            notes=model_config.notes
        )


# 辅助函数：兼容旧接口
def get_model_thinking_support(provider: str, model_name: str, registry: Optional[ModelRegistryV2] = None) -> bool:
    """获取模型是否支持thinking（兼容函数）"""
    if registry is None:
        # 如果没有提供registry，使用全局实例
        registry = global_model_registry_v2
    
    capabilities = registry.get_model_capabilities(provider, model_name, ModelType.CHAT)
    if capabilities and isinstance(capabilities, ChatCapabilities):
        return capabilities.supports_thinking
    
    return False


def get_model_can_toggle_thinking(provider: str, model_name: str, registry: Optional[ModelRegistryV2] = None) -> bool:
    """获取模型是否支持开关思维链"""
    if registry is None:
        registry = global_model_registry_v2
    
    capabilities = registry.get_model_capabilities(provider, model_name, ModelType.CHAT)
    if capabilities and isinstance(capabilities, ChatCapabilities):
        return capabilities.can_toggle_thinking
    
    return False


# 初始化全局注册表实例
def initialize_global_registry(providers_path: Optional[str] = None, models_path: Optional[str] = None) -> ModelRegistryV2:
    """初始化全局注册表"""
    import os
    
    # 默认配置路径
    if providers_path is None:
        # 优先从环境变量PROVIDERS_CONFIG读取
        providers_path = os.getenv("PROVIDERS_CONFIG")
        if providers_path is None:
            # 默认使用 Path(__file__).parents[2] / "config" / "providers.conf"
            providers_path = str(Path(__file__).parents[2] / "config" / "providers.conf")
    
    if models_path is None:
        # 优先从环境变量MODELS_CONFIG读取
        models_path = os.getenv("MODELS_CONFIG")
        if models_path is None:
            # 默认使用 Path(__file__).parents[2] / "config" / "models.conf"
            models_path = str(Path(__file__).parents[2] / "config" / "models.conf")
    
    registry = ModelRegistryV2(providers_path, models_path)
    return registry


# 全局实例
global_model_registry_v2 = initialize_global_registry()
# 向后兼容的别名
model_registry = global_model_registry_v2

