"""
适配器模块单元测试
"""

from __future__ import annotations

from datetime import UTC, datetime

from witty_mcp_manager.adapters import (
    BaseAdapter,
    SSEAdapter,
    STDIOAdapter,
    StreamableHTTPAdapter,
    Tool,
    ToolCallResult,
    ToolsCache,
)
from witty_mcp_manager.adapters.base import AdapterType


class TestTool:
    """Tool 数据类测试"""

    def test_tool_creation(self):
        """测试 Tool 创建"""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"arg1": {"type": "string"}}},
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert "arg1" in tool.input_schema["properties"]

    def test_tool_without_description(self):
        """测试无描述的 Tool"""
        tool = Tool(name="simple_tool")
        assert tool.name == "simple_tool"
        assert tool.description == ""  # 默认空字符串
        assert tool.input_schema == {}

    def test_tool_to_dict(self):
        """测试 Tool 转字典"""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
        )
        d = tool.to_dict()
        assert d["name"] == "test_tool"
        assert d["description"] == "A test tool"
        assert d["inputSchema"] == {"type": "object"}  # 注意是 inputSchema


class TestToolCallResult:
    """ToolCallResult 数据类测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolCallResult(
            success=True,
            content=[{"type": "text", "text": "Hello"}],
            duration_ms=100,
        )
        assert result.success is True
        assert len(result.content) == 1
        assert result.duration_ms == 100
        assert result.error is None

    def test_error_result(self):
        """测试错误结果"""
        result = ToolCallResult.error_result("Something went wrong", 50)
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.duration_ms == 50
        assert result.is_error is True
        # error_result 会将错误信息放入 content
        assert len(result.content) == 1
        assert result.content[0]["text"] == "Something went wrong"

    def test_result_to_dict(self):
        """测试结果转字典"""
        result = ToolCallResult(
            success=True,
            content=[{"type": "text", "text": "Hello"}],
            duration_ms=100,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["content"] == [{"type": "text", "text": "Hello"}]
        # duration_ms 不在 to_dict 中


class TestToolsCache:
    """ToolsCache 数据类测试"""

    def test_cache_creation(self):
        """测试缓存创建"""
        tools = [Tool(name="tool1"), Tool(name="tool2")]
        cache = ToolsCache(tools=tools, cached_at=datetime.now(UTC), ttl_seconds=300)
        assert len(cache.tools) == 2
        assert cache.ttl_seconds == 300

    def test_cache_not_expired(self):
        """测试缓存未过期"""
        tools = [Tool(name="tool1")]
        cache = ToolsCache(tools=tools, cached_at=datetime.now(UTC), ttl_seconds=300)
        assert not cache.is_expired

    def test_cache_expired(self):
        """测试缓存过期"""
        from datetime import timedelta

        tools = [Tool(name="tool1")]
        old_time = datetime.now(UTC) - timedelta(seconds=10)
        cache = ToolsCache(tools=tools, cached_at=old_time, ttl_seconds=5)
        assert cache.is_expired


class TestAdapterType:
    """AdapterType 枚举测试"""

    def test_adapter_types(self):
        """测试适配器类型"""
        assert AdapterType.STDIO.value == "stdio"
        assert AdapterType.SSE.value == "sse"
        assert AdapterType.STREAMABLE_HTTP.value == "streamable_http"


class TestBaseAdapter:
    """BaseAdapter 抽象类测试"""

    def test_base_adapter_is_abstract(self):
        """测试 BaseAdapter 是抽象类"""
        from abc import ABC

        assert issubclass(BaseAdapter, ABC)
        # 检查抽象方法
        assert hasattr(BaseAdapter, "connect")
        assert hasattr(BaseAdapter, "disconnect")
        assert hasattr(BaseAdapter, "discover_tools")
        assert hasattr(BaseAdapter, "call_tool")


class TestSTDIOAdapter:
    """STDIOAdapter 类测试"""

    def test_adapter_type(self):
        """测试适配器类型"""
        assert STDIOAdapter.adapter_type == AdapterType.STDIO

    def test_exports(self):
        """测试导出"""
        from witty_mcp_manager.adapters import STDIOAdapter

        assert STDIOAdapter is not None


class TestSSEAdapter:
    """SSEAdapter 类测试"""

    def test_adapter_type(self):
        """测试适配器类型"""
        assert SSEAdapter.adapter_type == AdapterType.SSE

    def test_exports(self):
        """测试导出"""
        from witty_mcp_manager.adapters import SSEAdapter

        assert SSEAdapter is not None


class TestStreamableHTTPAdapter:
    """StreamableHTTPAdapter 类测试"""

    def test_adapter_type(self):
        """测试适配器类型"""
        assert StreamableHTTPAdapter.adapter_type == AdapterType.STREAMABLE_HTTP

    def test_exports(self):
        """测试导出"""
        from witty_mcp_manager.adapters import StreamableHTTPAdapter

        assert StreamableHTTPAdapter is not None


class TestModuleExports:
    """模块导出测试"""

    def test_all_exports_available(self):
        """测试所有导出都可用"""
        from witty_mcp_manager import adapters

        assert hasattr(adapters, "BaseAdapter")
        assert hasattr(adapters, "STDIOAdapter")
        assert hasattr(adapters, "SSEAdapter")
        assert hasattr(adapters, "StreamableHTTPAdapter")
        assert hasattr(adapters, "Tool")
        assert hasattr(adapters, "ToolCallResult")
        assert hasattr(adapters, "ToolsCache")
        assert hasattr(adapters, "AdapterType")
