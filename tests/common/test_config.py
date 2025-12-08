"""Config类的单元测试"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import toml
from pydantic import ValidationError
from pytest_mock import MockerFixture

from apps.common.config import Config
from apps.schemas.config import ConfigModel

MOCK_CONFIG_DATA: dict[str, Any] = {
    "deploy": {"mode": "local", "cookie": "domain", "data_dir": "/app/data"},
    "rag": {"rag_service": "http://localhost"},
    "fastapi": {"domain": "localhost"},
    "minio": {
        "endpoint": "localhost:9000",
        "access_key": "test_key",
        "secret_key": "test_secret",
        "secure": False,
    },
    "postgres": {
        "host": "localhost",
        "port": 5432,
        "user": "test_user",
        "password": "test_password",
        "database": "test_db",
    },
    "security": {
        "half_key1": "test_key1",
        "half_key2": "test_key2",
        "half_key3": "test_key3",
        "jwt_key": "test_jwt_key",
    },
    "extra": {"sql_url": "http://localhost"},
}


@pytest.fixture(autouse=True)
def setup_teardown() -> Generator[None, None, None]:
    """测试前的准备工作和清理工作"""
    # 保存原始环境变量
    original_config = os.environ.get("CONFIG")
    original_prod = os.environ.get("PROD")

    # 清除环境变量
    if "CONFIG" in os.environ:
        del os.environ["CONFIG"]
    if "PROD" in os.environ:
        del os.environ["PROD"]

    yield

    # 测试后恢复环境变量
    if original_config is not None:
        os.environ["CONFIG"] = original_config
    elif "CONFIG" in os.environ:
        del os.environ["CONFIG"]

    if original_prod is not None:
        os.environ["PROD"] = original_prod
    elif "PROD" in os.environ:
        del os.environ["PROD"]


def test_init_with_default_config(mocker: MockerFixture, tmp_path: Path) -> None:
    """测试使用默认配置文件路径初始化"""
    # 创建临时配置文件
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml.dumps(MOCK_CONFIG_DATA))

    # Mock默认配置文件路径
    mocker.patch.object(Path, "__truediv__", return_value=config_file)
    mocker.patch("toml.load", return_value=MOCK_CONFIG_DATA)

    config = Config.init_config()

    assert isinstance(config, Config)
    assert isinstance(config, ConfigModel)
    assert config.deploy.mode == "local"
    assert config.deploy.data_dir == "/app/data"


def test_init_with_custom_config_path(mocker: MockerFixture, tmp_path: Path) -> None:
    """测试使用自定义配置文件路径初始化"""
    # 创建临时配置文件
    config_file = tmp_path / "custom_config.toml"
    config_file.write_text(toml.dumps(MOCK_CONFIG_DATA))

    # 设置自定义配置文件路径
    os.environ["CONFIG"] = str(config_file)

    mock_load = mocker.patch("toml.load", return_value=MOCK_CONFIG_DATA)

    config = Config.init_config()

    assert isinstance(config, Config)
    assert isinstance(config, ConfigModel)
    assert config.deploy.mode == "local"
    mock_load.assert_called_once_with(str(config_file))


def test_init_with_prod_env(mocker: MockerFixture, tmp_path: Path) -> None:
    """测试在PROD环境下初始化"""
    # 创建临时配置文件
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml.dumps(MOCK_CONFIG_DATA))

    # 设置PROD环境变量
    os.environ["PROD"] = "true"
    os.environ["CONFIG"] = str(config_file)

    mocker.patch("toml.load", return_value=MOCK_CONFIG_DATA)
    mock_unlink = mocker.patch.object(Path, "unlink")

    config = Config.init_config()

    assert isinstance(config, Config)
    assert isinstance(config, ConfigModel)
    mock_unlink.assert_called_once()


def test_config_immutability(mocker: MockerFixture, tmp_path: Path) -> None:
    """测试配置对象的不可变性"""
    # 创建临时配置文件
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml.dumps(MOCK_CONFIG_DATA))

    os.environ["CONFIG"] = str(config_file)
    mocker.patch("toml.load", return_value=MOCK_CONFIG_DATA)

    config = Config.init_config()

    # 验证配置是frozen的，无法修改
    with pytest.raises((ValidationError, AttributeError)):
        config.deploy.mode = "cloud"  # type: ignore[misc]


def test_config_fields(mocker: MockerFixture, tmp_path: Path) -> None:
    """测试配置字段的正确性"""
    # 创建临时配置文件
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml.dumps(MOCK_CONFIG_DATA))

    os.environ["CONFIG"] = str(config_file)
    mocker.patch("toml.load", return_value=MOCK_CONFIG_DATA)

    config = Config.init_config()

    # 验证所有字段
    assert config.deploy.mode == "local"
    assert config.deploy.cookie == "domain"
    assert config.deploy.data_dir == "/app/data"

    assert config.rag.rag_service == "http://localhost"

    assert config.fastapi.domain == "localhost"

    assert config.minio.endpoint == "localhost:9000"
    assert config.minio.access_key == "test_key"
    assert config.minio.secret_key == "test_secret"
    assert config.minio.secure is False

    assert config.postgres.host == "localhost"
    assert config.postgres.port == MOCK_CONFIG_DATA["postgres"]["port"]
    assert config.postgres.user == "test_user"
    assert config.postgres.password == "test_password"
    assert config.postgres.database == "test_db"

    assert config.security.half_key1 == "test_key1"
    assert config.security.half_key2 == "test_key2"
    assert config.security.half_key3 == "test_key3"
    assert config.security.jwt_key == "test_jwt_key"

    assert config.extra.sql_url == "http://localhost"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
