# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""模型注册表和配置管理"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """模型信息"""
    provider: str
    model_name: str
    supports_thinking: bool = False
    can_toggle_thinking: bool = False  # 是否支持开关思维链（仅当supports_thinking=True时有效）
    supports_function_calling: bool = True
    supports_json_mode: bool = True
    supports_structured_output: bool = False
    max_tokens_param: str = "max_tokens"
    notes: str = ""


class ModelRegistry:
    """模型注册表"""
    
    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._load_default_models()
    
    def _load_default_models(self):
        """加载默认模型配置"""
        default_models = [
            # OpenAI模型
            ModelInfo("openai", "gpt-4o", supports_thinking=False),
            ModelInfo("openai", "gpt-4o-mini", supports_thinking=False),
            ModelInfo("openai", "o1-preview", supports_thinking=True, can_toggle_thinking=True, max_tokens_param="max_completion_tokens"),
            ModelInfo("openai", "o1-mini", supports_thinking=True, can_toggle_thinking=True, max_tokens_param="max_completion_tokens"),
            
            # 阿里百炼Qwen模型
            ModelInfo("qwen", "qwen-plus", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("qwen", "qwen-turbo", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("qwen", "qwen2.5-72b-instruct", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("qwen", "qwen2.5-32b-instruct", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("qwen", "qwen2.5-14b-instruct", supports_thinking=False),
            ModelInfo("qwen", "qwen2.5-7b-instruct", supports_thinking=False),
            
            # SiliconFlow模型
            ModelInfo("siliconflow", "qwen2.5-coder-32b-instruct", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("siliconflow", "qwen2.5-72b-instruct", supports_thinking=True, can_toggle_thinking=True),
            ModelInfo("siliconflow", "Qwen/Qwen3-8B", supports_thinking=True, can_toggle_thinking=True),  # Qwen3-8B支持enable_thinking
            ModelInfo("siliconflow", "deepseek-v2.5", supports_thinking=True, can_toggle_thinking=False),  # DeepSeek系列不支持关闭思维链
            ModelInfo("siliconflow", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", supports_thinking=False),  # 该模型不支持enable_thinking参数
            ModelInfo("siliconflow", "yi-lightning", supports_thinking=False),
            ModelInfo("siliconflow", "glm-4-9b-chat", supports_thinking=False),
            
            # DeepSeek模型
            ModelInfo("deepseek", "deepseek-chat", supports_thinking=False),
            ModelInfo("deepseek", "deepseek-reasoner", supports_thinking=True, can_toggle_thinking=False),  # DeepSeek系列不支持关闭思维链
            ModelInfo("deepseek", "deepseek-r1", supports_thinking=True, can_toggle_thinking=False),  # DeepSeek系列不支持关闭思维链
            
            # 腾讯混元模型
            ModelInfo("tencent", "hunyuan-lite", supports_thinking=False),
            ModelInfo("tencent", "hunyuan-standard", supports_thinking=False),
            ModelInfo("tencent", "hunyuan-pro", supports_thinking=False),
            ModelInfo("tencent", "hunyuan-MT-7B", supports_thinking=False),
            ModelInfo("tencent", "hunyuan-turbo", supports_thinking=False),
            
            # 其他提供商的默认配置
            ModelInfo("baichuan", "baichuan2-turbo", supports_thinking=False),
            ModelInfo("spark", "spark-lite", supports_thinking=False),
            ModelInfo("wenxin", "ernie-4.0-turbo-8k", supports_thinking=False),
        ]
        
        for model in default_models:
            self.register_model(model)
    
    def register_model(self, model_info: ModelInfo):
        """注册模型"""
        key = f"{model_info.provider}:{model_info.model_name}"
        self._models[key] = model_info
        logger.debug(f"注册模型: {key}")
    
    def get_model_info(self, provider: str, model_name: str) -> Optional[ModelInfo]:
        """获取模型信息，支持智能推断"""
        key = f"{provider}:{model_name}"
        
        # 1. 直接匹配
        if key in self._models:
            return self._models[key]
        
        # 2. 相同模型名不同供应商的能力匹配
        model_info = self._find_by_model_name(model_name)
        if model_info:
            logger.debug(f"通过模型名匹配找到能力信息: {provider}:{model_name} -> {model_info.provider}:{model_info.model_name}")
            return model_info
        
        # 3. 系列推断逻辑
        model_info = self._infer_by_series(provider, model_name)
        if model_info:
            logger.debug(f"通过系列推断找到能力信息: {provider}:{model_name} -> 系列匹配")
            return model_info
        
        return None
    
    def _find_by_model_name(self, model_name: str) -> Optional[ModelInfo]:
        """通过模型名查找相同模型的能力信息"""
        for model_info in self._models.values():
            if model_info.model_name == model_name:
                return model_info
        return None
    
    def _infer_by_series(self, provider: str, model_name: str) -> Optional[ModelInfo]:
        """通过系列推断模型能力"""
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
                "reference_models": ["qwen2.5-72b-instruct", "qwen2.5-32b-instruct"],
                "series_name": "Qwen2.5"
            },
            {
                "patterns": ["qwen3", "qwen-3"],
                "reference_models": ["qwen2.5-72b-instruct"],  # 使用qwen2.5作为参考
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
                "reference_models": ["deepseek-v2.5"],
                "series_name": "DeepSeek-V"
            },
            # 其他系列
            {
                "patterns": ["yi-"],
                "reference_models": ["yi-lightning"],
                "series_name": "Yi"
            },
            {
                "patterns": ["glm-4", "glm4"],
                "reference_models": ["glm-4-9b-chat"],
                "series_name": "GLM-4"
            },
            {
                "patterns": ["baichuan2", "baichuan-2"],
                "reference_models": ["baichuan2-turbo"],
                "series_name": "Baichuan2"
            },
            {
                "patterns": ["ernie-4", "ernie4"],
                "reference_models": ["ernie-4.0-turbo-8k"],
                "series_name": "ERNIE-4"
            },
            # 腾讯混元系列
            {
                "patterns": ["hunyuan", "混元"],
                "reference_models": ["hunyuan-MT-7B", "hunyuan-pro"],
                "series_name": "Hunyuan"
            }
        ]
        
        # 查找匹配的系列
        for rule in series_rules:
            for pattern in rule["patterns"]:
                if pattern in model_lower:
                    # 找到匹配的系列，使用参考模型的能力
                    for ref_model in rule["reference_models"]:
                        ref_info = self._find_by_model_name(ref_model)
                        if ref_info:
                            logger.debug(f"系列推断: {model_name} 匹配 {rule['series_name']} 系列，参考模型: {ref_model}")
                            # 创建新的ModelInfo，保持原有provider和model_name
                            return ModelInfo(
                                provider=provider,
                                model_name=model_name,
                                supports_thinking=ref_info.supports_thinking,
                                can_toggle_thinking=ref_info.can_toggle_thinking,
                                supports_function_calling=ref_info.supports_function_calling,
                                supports_json_mode=ref_info.supports_json_mode,
                                supports_structured_output=ref_info.supports_structured_output,
                                max_tokens_param=ref_info.max_tokens_param,
                                notes=f"基于{rule['series_name']}系列推断，参考模型: {ref_model}"
                            )
        
        return None
    
    def list_models_by_provider(self, provider: str) -> List[ModelInfo]:
        """按提供商列出模型"""
        return [model for model in self._models.values() if model.provider == provider]
    
    def export_config(self) -> Dict:
        """导出配置"""
        return {
            "models": {key: asdict(model) for key, model in self._models.items()},
            "version": "1.0"
        }
    
    def import_config(self, config: Dict):
        """导入配置"""
        if "models" in config:
            for key, model_data in config["models"].items():
                model_info = ModelInfo(**model_data)
                self._models[key] = model_info
    
    def save_to_file(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.export_config(), f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, filepath: str):
        """从文件加载"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.import_config(config)
        except FileNotFoundError:
            logger.warning(f"模型配置文件不存在: {filepath}")
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")


# 全局模型注册表实例
model_registry = ModelRegistry()


def get_model_thinking_support(provider: str, model_name: str) -> bool:
    """获取模型是否支持thinking（使用智能推断）"""
    model_info = model_registry.get_model_info(provider, model_name)
    if model_info:
        return model_info.supports_thinking
    
    # 如果智能推断也没有找到，使用保守的默认值
    logger.debug(f"未找到模型 {provider}:{model_name} 的能力信息，默认不支持thinking")
    return False


def update_siliconflow_model_support():
    """更新SiliconFlow模型支持情况"""
    # 支持thinking的模型
    siliconflow_thinking_models = [
        "qwen2.5-coder-32b-instruct",
        "qwen2.5-72b-instruct", 
        "deepseek-v2.5",
        # 可以根据实际测试结果添加更多模型
    ]
    
    # 支持thinking但需要特殊处理的模型
    siliconflow_special_thinking_models = [
        "Qwen/Qwen3-8B",
        # 可以根据实际测试结果添加更多模型
    ]
    
    # 注册支持thinking的模型
    for model_name in siliconflow_thinking_models:
        # 根据模型类型设置can_toggle_thinking
        can_toggle = not model_name.startswith("deepseek")  # DeepSeek系列不支持关闭思维链
        model_info = ModelInfo(
            provider="siliconflow",
            model_name=model_name,
            supports_thinking=True,
            can_toggle_thinking=can_toggle,
            notes="经过测试确认支持thinking"
        )
        model_registry.register_model(model_info)
    
    # 注册特殊thinking模型
    for model_name in siliconflow_special_thinking_models:
        model_info = ModelInfo(
            provider="siliconflow",
            model_name=model_name,
            supports_thinking=True,
            can_toggle_thinking=True,
            notes="支持thinking，根据SiliconFlow平台确认"
        )
        model_registry.register_model(model_info)


# 初始化时更新SiliconFlow配置
update_siliconflow_model_support()


def get_model_thinking_support(provider: str, model_name: str) -> bool:
    """获取模型的思维链支持情况"""
    model_info = model_registry.get_model_info(provider, model_name)
    if model_info:
        return model_info.supports_thinking
    return False
