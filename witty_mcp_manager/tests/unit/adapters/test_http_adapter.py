"""StreamableHTTPAdapter 单元测试

覆盖 adapters/http.py 中的所有方法。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from witty_mcp_manager.adapters.base import AdapterType
from witty_mcp_manager.adapters.http import StreamableHTTPAdapter
from witty_mcp_manager.exceptions import AdapterError


@pytest.fixture
def http_adapter() -> StreamableHTTPAdapter:
    """创建 HTTP 适配器实例"""
    server = MagicMock()
    server.id = "test_http_server"
    config = MagicMock()
    return StreamableHTTPAdapter(server, config)


class TestStreamableHTTPAdapter:
    """StreamableHTTPAdapter 测试"""

    def test_adapter_type(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试 adapter_type 属性"""
        assert http_adapter.adapter_type == AdapterType.STREAMABLE_HTTP

    @pytest.mark.asyncio
    async def test_connect_raises(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试 connect 抛出 AdapterError"""
        session = MagicMock()
        with pytest.raises(AdapterError, match="not implemented"):
            await http_adapter.connect(session)

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试未连接时 disconnect 不做任何操作"""
        await http_adapter.disconnect()
        assert not http_adapter.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试已连接时 disconnect 清理状态"""
        http_adapter._connected = True  # noqa: SLF001
        await http_adapter.disconnect()
        assert not http_adapter.is_connected

    @pytest.mark.asyncio
    async def test_discover_tools_raises(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试 discover_tools 抛出 AdapterError"""
        with pytest.raises(AdapterError, match="not implemented"):
            await http_adapter.discover_tools()

    @pytest.mark.asyncio
    async def test_discover_tools_force_refresh_raises(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试 force_refresh 也抛出异常"""
        with pytest.raises(AdapterError, match="not implemented"):
            await http_adapter.discover_tools(force_refresh=True)

    @pytest.mark.asyncio
    async def test_call_tool_raises(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试 call_tool 抛出 AdapterError"""
        with pytest.raises(AdapterError, match="not implemented"):
            await http_adapter.call_tool("test_tool", {"arg": "val"})

    @pytest.mark.asyncio
    async def test_call_tool_with_timeout_raises(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试带超时的 call_tool 也抛出异常"""
        with pytest.raises(AdapterError, match="not implemented"):
            await http_adapter.call_tool("test_tool", {}, timeout_ms=5000)

    def test_is_not_connected_initially(self, http_adapter: StreamableHTTPAdapter) -> None:
        """测试初始状态为未连接"""
        assert not http_adapter.is_connected
