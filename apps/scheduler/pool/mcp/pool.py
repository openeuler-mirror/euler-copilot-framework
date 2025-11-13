# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP池；下属于Pool，单例"""

import logging

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.constants import MCP_PATH
from apps.models import MCPActivated, MCPType
from apps.schemas.mcp import MCPServerConfig

from .client import MCPClient

logger = logging.getLogger(__name__)
MCP_USER_PATH = MCP_PATH / "users"


class _MCPPool:
    """MCP池（内部类）"""

    def __init__(self) -> None:
        """初始化MCP池"""
        self.pool: dict[str, dict[str, MCPClient]] = {}


    async def init_mcp(self, mcp_id: str, user_id: str) -> MCPClient | None:
        """初始化MCP池"""
        config_path = MCP_USER_PATH / user_id / mcp_id / "config.json"

        flag = (await config_path.exists())
        if not flag:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 配置文件不存在", user_id, mcp_id)
            return None

        config = MCPServerConfig.model_validate_json(await config_path.read_text())

        if config.mcpType in (MCPType.SSE, MCPType.STDIO):
            client = MCPClient()
        else:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 类型错误", user_id, mcp_id)
            return None

        await client.init(user_id, mcp_id, config.mcpServers[mcp_id])
        if user_id not in self.pool:
            self.pool[user_id] = {}
        self.pool[user_id][mcp_id] = client
        return client


    async def _get_from_dict(self, mcp_id: str, user_id: str) -> MCPClient | None:
        """从字典中获取MCP客户端"""
        if user_id not in self.pool:
            return None

        if mcp_id not in self.pool[user_id]:
            return None

        return self.pool[user_id][mcp_id]


    async def _validate_user(self, mcp_id: str, user_id: str) -> bool:
        """验证用户是否已激活"""
        async with postgres.session() as session:
            result = (await session.scalars(
                select(MCPActivated).where(
                    and_(
                        MCPActivated.mcpId == mcp_id,
                        MCPActivated.userId == user_id,
                    ),
                ).limit(1),
            )).one_or_none()
            return result is not None


    async def get(self, mcp_id: str, user_id: str) -> MCPClient:
        """获取MCP客户端，如果无法获取则抛出异常"""
        item = await self._get_from_dict(mcp_id, user_id)
        if item is None:
            # 检查用户是否已激活
            if not await self._validate_user(mcp_id, user_id):
                err = f"用户 {user_id} 未激活MCP {mcp_id}"
                logger.warning(err)
                raise RuntimeError(err)

            # 初始化进程
            item = await self.init_mcp(mcp_id, user_id)
            if item is None:
                err = f"初始化MCP {mcp_id} 失败（用户：{user_id}）"
                logger.error(err)
                raise RuntimeError(err)

            if user_id not in self.pool:
                self.pool[user_id] = {}

            self.pool[user_id][mcp_id] = item

        return item


    async def stop(self, mcp_id: str, user_id: str) -> None:
        """停止MCP客户端"""
        if user_id not in self.pool:
            logger.warning("[MCPPool] 用户 %s 不存在于池中，无法停止MCP %s", user_id, mcp_id)
            return

        if mcp_id not in self.pool[user_id]:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 不存在于池中，无法停止", user_id, mcp_id)
            return

        await self.pool[user_id][mcp_id].stop()
        del self.pool[user_id][mcp_id]


# 创建单例对象
mcp_pool = _MCPPool()
