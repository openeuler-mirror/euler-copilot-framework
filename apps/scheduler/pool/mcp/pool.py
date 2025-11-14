# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP池"""

import logging

from apps.common.mongo import MongoDB
from apps.common.singleton import SingletonMeta
from apps.constants import MCP_PATH
from apps.schemas.mcp import MCPServerConfig, MCPType

from .client import MCPClient

logger = logging.getLogger(__name__)
MCP_USER_PATH = MCP_PATH / "users"


class MCPPool(metaclass=SingletonMeta):
    """MCP池"""

    def __init__(self) -> None:
        """初始化MCP池"""
        self.pool = {}

    async def _init_mcp(self, mcp_id: str, user_sub: str) -> MCPClient | None:
        """初始化MCP池"""
        config_path = MCP_USER_PATH / user_sub / mcp_id / "config.json"
        flag = (await config_path.exists())
        if not flag:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 配置文件不存在", user_sub, mcp_id)
            return None
        config = MCPServerConfig.model_validate_json(await config_path.read_text())

        if config.type in (MCPType.SSE, MCPType.STDIO):
            client = MCPClient()
        else:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 类型错误", user_sub, mcp_id)
            return None

        await client.init(user_sub, mcp_id, config.config)
        if user_sub not in self.pool:
            self.pool[user_sub] = {}
        self.pool[user_sub][mcp_id] = client
        return client

    async def _get_from_dict(self, mcp_id: str, user_sub: str) -> MCPClient | None:
        """从字典中获取MCP客户端"""
        if user_sub not in self.pool:
            return None

        if mcp_id not in self.pool[user_sub]:
            return None

        return self.pool[user_sub][mcp_id]

    async def _validate_user(self, mcp_id: str, user_sub: str) -> bool:
        """验证用户是否已激活"""
        mcp_collection = MongoDB.get_collection("mcp")
        mcp_db_result = await mcp_collection.find_one({"_id": mcp_id, "activated": user_sub})
        return mcp_db_result is not None

    async def get(self, mcp_id: str, user_sub: str) -> MCPClient | None:
        """获取MCP客户端"""
        item = await self._get_from_dict(mcp_id, user_sub)
        if item is None:
            # 检查用户是否已激活
            if not await self._validate_user(mcp_id, user_sub):
                logger.warning("用户 %s 未激活MCP %s", user_sub, mcp_id)
                return None

            # 初始化进程
            item = await self._init_mcp(mcp_id, user_sub)
            if item is None:
                return None

            if user_sub not in self.pool:
                self.pool[user_sub] = {}

            self.pool[user_sub][mcp_id] = item

        return item

    async def stop(self, mcp_id: str, user_sub: str) -> None:
        """停止MCP客户端"""
        if user_sub not in self.pool:
            logger.warning("[MCPPool] 用户 %s 不在池中，无法停止", user_sub)
            return
        if mcp_id not in self.pool[user_sub]:
            logger.warning(
                "[MCPPool] MCP %s 不在用户 %s 的池中，无法停止", mcp_id, user_sub)
            return
        await self.pool[user_sub][mcp_id].stop()
        del self.pool[user_sub][mcp_id]
