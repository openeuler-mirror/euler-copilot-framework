"""Config类的单元测试"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import toml
from pytest_mock import MockerFixture

from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.schemas.config import ConfigModel

MOCK_CONFIG_DATA: dict[str, Any] = {
    "deploy": {"mode": "local", "cookie": "domain", "data_dir": "/app/data"},
    "login": {
        "provider": "authhub",
        "settings": {
            "host": "http://localhost",
            "host_inner": "http://localhost",
            "login_api": "http://localhost/api/auth/login",
            "app_id": "test_id",
            "app_secret": "test_secret",
        },
    },
    "embedding": {
        "type": "openai",
        "endpoint": "http://localhost",
        "api_key": "test_key",
        "model": "test_model",
    },
    "rag": {"rag_service": "http://localhost"},
    "fastapi": {"domain": "localhost", "session_ttl": 30, "csrf": False},
    "minio": {
        "endpoint": "localhost:9000",
        "access_key": "test_key",
        "secret_key": "test_secret",
        "secure": False,
    },
    "mongodb": {
        "host": "localhost",
        "port": 27017,
        "user": "test_user",
        "password": "test_password",
        "database": "test_db",
    },
    "llm": {
        "key": "test_key",
        "endpoint": "http://localhost",
        "model": "test_model",
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "function_call": {
        "backend": "test_backend",
        "model": "test_model",
        "endpoint": "http://localhost",
        "api_key": "test_key",
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "security": {
        "half_key1": "test_key1",
        "half_key2": "test_key2",
        "half_key3": "test_key3",
        "jwt_key": "test_jwt_key",
    },
    "check": {"enable": False, "words_list": ""},
    "sandbox": {"sandbox_service": "http://localhost:8000"},
    "extra": {"sql_url": "http://localhost"},
}


@pytest.fixture(autouse=True)
def setup_teardown() -> Generator[None, None, None]:
    """测试前的准备工作和清理工作"""
    # 清除单例实例
    SingletonMeta._instances.clear()
    # 清除环境变量
    if "CONFIG" in os.environ:
        del os.environ["CONFIG"]
    if "PROD" in os.environ:
        del os.environ["PROD"]
    yield
    # 测试后的清理工作
    SingletonMeta._instances.clear()


def test_init_with_default_config(mocker: MockerFixture) -> None:
    """测试使用默认配置文件路径初始化"""
    mocker.patch("builtins.open", mocker.mock_open(read_data=toml.dumps(MOCK_CONFIG_DATA)))
    config = Config()
    assert isinstance(config._config, ConfigModel)
    assert config._config.deploy.mode == "local"


def test_init_with_custom_config_path(mocker: MockerFixture) -> None:
    """测试使用自定义配置文件路径初始化"""
    custom_path = "/custom/path/config.toml"
    os.environ["CONFIG"] = custom_path

    mocker.patch("builtins.open", mocker.mock_open(read_data=toml.dumps(MOCK_CONFIG_DATA)))
    config = Config()
    assert isinstance(config._config, ConfigModel)
    assert config._config.deploy.mode == "local"


def test_init_with_prod_env(mocker: MockerFixture) -> None:
    """测试在PROD环境下初始化"""
    os.environ["PROD"] = "true"

    mocker.patch("builtins.open", mocker.mock_open(read_data=toml.dumps(MOCK_CONFIG_DATA)))
    mock_unlink = mocker.patch.object(Path, "unlink")
    config = Config()
    assert isinstance(config._config, ConfigModel)
    mock_unlink.assert_called_once()


def test_get_config(mocker: MockerFixture) -> None:
    """测试获取配置"""
    mocker.patch("builtins.open", mocker.mock_open(read_data=toml.dumps(MOCK_CONFIG_DATA)))
    config = Config()
    config_copy = config.get_config()
    assert isinstance(config_copy, ConfigModel)
    assert config_copy is not config._config  # 确保返回的是深拷贝


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
