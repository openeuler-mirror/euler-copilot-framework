import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 配置缓存
_config: Optional[Dict[str, Any]] = None
_config_file_path = "rag_config.json"


def _load_config() -> Dict[str, Any]:
    """
    加载配置文件
    :return: 配置字典
    """
    global _config
    
    if _config is not None:
        return _config
    
    default_config = {
        "embedding": {
            "type": "openai",
            "api_key": "",
            "endpoint": "",
            "model_name": "text-embedding-ada-002",
            "timeout": 30,
            "vector_dimension": 1024
        },
        "token": {
            "model": "gpt-4",
            "max_tokens": 8192,
            "default_chunk_size": 1024
        },
        "search": {
            "default_top_k": 5,
            "max_top_k": 100
        }
    }
    
    config_file = _get_config_file_path()
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # 合并配置（文件配置优先）
                _config = _merge_config(default_config, file_config)
        except Exception as e:
            logger.warning(f"[Config] 加载配置文件失败: {e}")
            _config = default_config
    else:
        _config = default_config
    
    _apply_env_overrides(_config)
    
    return _config


def _cfg() -> Dict[str, Any]:
    return _load_config()


def _get_config_file_path() -> str:
    """
    获取配置文件路径
    优先使用项目根目录下的 rag_config.json
    :return: 配置文件路径
    """
    # 尝试从项目根目录查找
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file = os.path.join(current_dir, _config_file_path)
    if os.path.exists(config_file):
        return config_file
    
    # 尝试从当前工作目录查找
    cwd_config = os.path.join(os.getcwd(), _config_file_path)
    if os.path.exists(cwd_config):
        return cwd_config
    
    # 返回项目根目录路径（即使文件不存在）
    return config_file


def _merge_config(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并配置字典（递归合并）
    :param default: 默认配置
    :param override: 覆盖配置
    :return: 合并后的配置
    """
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]):
    """
    应用环境变量覆盖（优先级最高）
    :param config: 配置字典
    """
    if os.getenv("EMBEDDING_TYPE"):
        config["embedding"]["type"] = os.getenv("EMBEDDING_TYPE")
    if os.getenv("EMBEDDING_API_KEY"):
        config["embedding"]["api_key"] = os.getenv("EMBEDDING_API_KEY")
    if os.getenv("EMBEDDING_ENDPOINT"):
        config["embedding"]["endpoint"] = os.getenv("EMBEDDING_ENDPOINT")
    if os.getenv("EMBEDDING_MODEL_NAME"):
        config["embedding"]["model_name"] = os.getenv("EMBEDDING_MODEL_NAME")
    
    if os.getenv("TOKEN_MODEL"):
        config["token"]["model"] = os.getenv("TOKEN_MODEL")
    if os.getenv("MAX_TOKENS"):
        try:
            config["token"]["max_tokens"] = int(os.getenv("MAX_TOKENS"))
        except ValueError:
            pass
    if os.getenv("DEFAULT_CHUNK_SIZE"):
        try:
            config["token"]["default_chunk_size"] = int(os.getenv("DEFAULT_CHUNK_SIZE"))
        except ValueError:
            pass


def get_embedding_type() -> str:
    return _cfg()["embedding"]["type"]


def get_embedding_api_key() -> str:
    return _cfg()["embedding"]["api_key"]


def get_embedding_endpoint() -> str:
    return _cfg()["embedding"]["endpoint"]


def get_embedding_model_name() -> str:
    return _cfg()["embedding"]["model_name"]


def get_embedding_timeout() -> int:
    return _cfg()["embedding"]["timeout"]


def get_embedding_vector_dimension() -> int:
    return _cfg()["embedding"]["vector_dimension"]


def get_token_model() -> str:
    return _cfg()["token"]["model"]


def get_max_tokens() -> int:
    return _cfg()["token"]["max_tokens"]


def get_default_chunk_size() -> int:
    return _cfg()["token"]["default_chunk_size"]


def get_default_top_k() -> int:
    return _cfg()["search"]["default_top_k"]


def reload_config():
    """当 rag_config.json 更新后重新加载缓存"""
    global _config
    _config = None

