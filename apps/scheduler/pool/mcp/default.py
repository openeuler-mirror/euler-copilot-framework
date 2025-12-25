# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 默认配置"""

import logging
import uuid

from apps.schemas.mcp import (
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPType,
)

logger = logging.getLogger(__name__)

def _default_stdio_config(hex_id: str) -> MCPServerConfig:
    """默认的Stdio协议MCP Server配置"""
    return MCPServerConfig(
        name="MCP服务_" + hex_id,
        description="MCP服务描述",
        mcpType=MCPType.STDIO,
        mcpServers={
            f"MCP_{hex_id}": MCPServerStdioConfig(
            command="uvx",
            args=[
                "your_package",
            ],
            env={
                "EXAMPLE_ENV": "example_value",
            },
        ),
    },
)


def _default_sse_config(hex_id: str) -> MCPServerConfig:
    """默认的SSE协议MCP Server配置"""
    return MCPServerConfig(
        name="MCP服务_" + hex_id,
        description="MCP服务描述",
        mcpType=MCPType.SSE,
        mcpServers={
            f"MCP_{hex_id}": MCPServerSSEConfig(
                url="http://test.domain/sse",
                headers={
                    "EXAMPLE_HEADER": "example_value",
                },
            ),
        },
    )


async def get_default(mcp_type: MCPType) -> MCPServerConfig:
    """
    用于获取默认的 MCP 配置

    :param MCPType mcp_type: MCP类型
    :return: MCP配置
    :rtype: MCPConfig
    :raises ValueError: 未找到默认的 MCP 配置
    """
    random_id = uuid.uuid4().hex[:6]

    if mcp_type == MCPType.STDIO:
        return _default_stdio_config(random_id)
    if mcp_type == MCPType.SSE:
        return _default_sse_config(random_id)
    err = f"未找到默认的 MCP 配置: {mcp_type}"
    logger.error(err)
    raise ValueError(err)
