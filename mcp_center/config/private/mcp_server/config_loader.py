# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
from config.public.base_config_loader import BaseConfig, project_root
import os
from pydantic import BaseModel, Field
import toml


class McpServerConfigModel(BaseModel):
    """顶层配置模型"""
    port: int = Field(default=12555, description="MCP服务端口")
    fastapi_port : int = Field(default=12556, description="fastapi服务端口")
    llm_remote: str = Field(default="", description="LLM远程主机地址")
    llm_model: str = Field(default="gpt-3.5-turbo", description="LLM模型名称")
    llm_api_key: str = Field(default="", description="LLM API Key")
    max_tokens: int = Field(default=2048, description="LLM最大Token数")
    temperature: float = Field(default=0.7, description="LLM温度参数")

class McpServerConfig(BaseConfig):
    """顶层配置文件读取和使用Class"""

    def __init__(self) -> None:
        """读取配置文件"""
        super().__init__()
        self.load_private_config()

    def load_private_config(self) -> None:
        """加载私有配置文件"""
        config_file = os.getenv("MCP_SERVER_CONFIG")
        if config_file is None:
            config_file = os.path.join(project_root,"config", "private", "mcp_server", "config.toml")
        self._config.private_config = McpServerConfigModel.model_validate(toml.load(config_file))

