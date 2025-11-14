# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
from config.public.base_config_loader import BaseConfig
import os
from pydantic import BaseModel, Field
import toml


class NpuSmiConfigModel(BaseModel):
    """顶层配置模型"""
    port: int = Field(default=12115, description="MCP服务端口")


class NpuSmiConfig(BaseConfig):
    """顶层配置文件读取和使用Class"""

    def __init__(self) -> None:
        """读取配置文件"""
        super().__init__()
        self.load_private_config()

    def load_private_config(self) -> None:
        """加载私有配置文件"""
        config_file = os.getenv("NPU_SMI_CONFIG")
        if config_file is None:
            config_file = os.path.join("config", "private", "npu", "config.toml")
        self._config.private_config = NpuSmiConfigModel.model_validate(toml.load(config_file))
