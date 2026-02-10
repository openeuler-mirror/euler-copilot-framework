"""
全局工具缓存测试

验证全局缓存机制的正确性
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from witty_mcp_manager.adapters.base import (
    Tool,
    clear_global_cache,
    get_cache_lock,
    get_global_cached_tools,
    update_global_cached_tools,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前清空全局缓存"""
    clear_global_cache()
    yield
    clear_global_cache()


@pytest.mark.asyncio
class TestGlobalToolsCache:
    """全局工具缓存测试"""

    async def test_cache_miss_returns_none(self):
        """缓存未命中返回 None"""
        result = await get_global_cached_tools("test_mcp", ttl_seconds=600)
        assert result is None

    async def test_cache_hit_returns_tools(self):
        """缓存命中返回工具列表"""
        tools = [
            Tool(name="tool1", description="desc1"),
            Tool(name="tool2", description="desc2"),
        ]

        await update_global_cached_tools("test_mcp", tools)
        cached = await get_global_cached_tools("test_mcp", ttl_seconds=600)

        assert cached is not None
        assert len(cached) == 2
        assert cached[0].name == "tool1"
        assert cached[1].name == "tool2"

    async def test_cache_returns_copy(self):
        """缓存返回防御性拷贝"""
        tools = [Tool(name="tool1", description="desc1")]

        await update_global_cached_tools("test_mcp", tools)
        cached1 = await get_global_cached_tools("test_mcp", ttl_seconds=600)
        cached2 = await get_global_cached_tools("test_mcp", ttl_seconds=600)

        # 应该是不同的对象
        assert cached1 is not cached2
        # 但内容相同
        assert cached1 == cached2

    async def test_cache_expiration(self):
        """缓存过期测试"""
        tools = [Tool(name="tool1", description="desc1")]

        await update_global_cached_tools("test_mcp", tools)

        # 未过期
        cached = await get_global_cached_tools("test_mcp", ttl_seconds=600)
        assert cached is not None

        # 模拟过期（TTL = 0）
        cached = await get_global_cached_tools("test_mcp", ttl_seconds=0)
        assert cached is None

    async def test_force_refresh_ignores_cache(self):
        """强制刷新忽略缓存"""
        tools = [Tool(name="tool1", description="desc1")]

        await update_global_cached_tools("test_mcp", tools)

        # 强制刷新应返回 None
        cached = await get_global_cached_tools(
            "test_mcp", ttl_seconds=600, force_refresh=True
        )
        assert cached is None

    async def test_multiple_mcp_servers(self):
        """多个 MCP Server 独立缓存"""
        tools1 = [Tool(name="tool1", description="desc1")]
        tools2 = [Tool(name="tool2", description="desc2")]

        await update_global_cached_tools("mcp1", tools1)
        await update_global_cached_tools("mcp2", tools2)

        cached1 = await get_global_cached_tools("mcp1", ttl_seconds=600)
        cached2 = await get_global_cached_tools("mcp2", ttl_seconds=600)

        assert cached1 is not None
        assert cached2 is not None
        assert len(cached1) == 1
        assert len(cached2) == 1
        assert cached1[0].name == "tool1"
        assert cached2[0].name == "tool2"

    async def test_clear_specific_cache(self):
        """清除特定 MCP Server 的缓存"""
        tools1 = [Tool(name="tool1", description="desc1")]
        tools2 = [Tool(name="tool2", description="desc2")]

        await update_global_cached_tools("mcp1", tools1)
        await update_global_cached_tools("mcp2", tools2)

        clear_global_cache("mcp1")

        cached1 = await get_global_cached_tools("mcp1", ttl_seconds=600)
        cached2 = await get_global_cached_tools("mcp2", ttl_seconds=600)

        assert cached1 is None
        assert cached2 is not None

    async def test_clear_all_cache(self):
        """清除所有缓存"""
        tools1 = [Tool(name="tool1", description="desc1")]
        tools2 = [Tool(name="tool2", description="desc2")]

        await update_global_cached_tools("mcp1", tools1)
        await update_global_cached_tools("mcp2", tools2)

        clear_global_cache()

        cached1 = await get_global_cached_tools("mcp1", ttl_seconds=600)
        cached2 = await get_global_cached_tools("mcp2", ttl_seconds=600)

        assert cached1 is None
        assert cached2 is None

    async def test_concurrent_access_with_lock(self):
        """并发访问使用锁保护"""
        lock = await get_cache_lock("test_mcp")

        async def update_with_delay():
            async with lock:
                await asyncio.sleep(0.1)
                await update_global_cached_tools(
                    "test_mcp", [Tool(name="delayed", description="desc")]
                )

        # 启动延迟更新任务
        task = asyncio.create_task(update_with_delay())

        # 等待一小段时间确保任务获取了锁
        await asyncio.sleep(0.01)

        # 尝试获取锁（应该等待）
        start = datetime.now(UTC)
        async with lock:
            elapsed = (datetime.now(UTC) - start).total_seconds()
            # 应该等待了至少 0.09 秒（0.1 - 0.01）
            assert elapsed >= 0.08

        await task
