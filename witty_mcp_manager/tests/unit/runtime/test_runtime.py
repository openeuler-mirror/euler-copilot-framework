"""
Runtime 模块单元测试
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from witty_mcp_manager.registry.models import (
    NormalizedConfig,
    ServerRecord,
    SourceType,
    StdioConfig,
    Timeouts,
    TransportType,
)
from witty_mcp_manager.runtime.manager import RuntimeManager, Session
from witty_mcp_manager.runtime.recycle import SessionRecycler


class TestSession:
    """Session 测试"""

    @pytest.fixture
    def sample_server(self) -> ServerRecord:
        """创建示例 ServerRecord"""
        return ServerRecord(
            id="git_mcp",
            name="Git MCP Server",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/git_mcp",
            upstream_key="git_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """创建模拟的 EffectiveConfig"""
        config = MagicMock()
        config.timeouts = Timeouts(tool_call=30, idle_ttl=600)
        return config

    def test_session_key(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试会话键生成"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )
        assert session.session_key == "user123:git_mcp"

    def test_initial_state(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试初始状态"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )
        assert session.state.status == "stopped"
        assert session.is_running is False

    @pytest.mark.asyncio
    async def test_start(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试启动"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )

        await session.start()

        assert session.state.status == "starting"
        assert session.state.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_running(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试标记运行中"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )

        await session.mark_running(pid=12345)

        assert session.state.status == "running"
        assert session.state.pid == 12345
        assert session.is_running is True

    @pytest.mark.asyncio
    async def test_stop(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试停止"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )

        await session.mark_running(pid=12345)
        await session.stop()

        assert session.state.status == "stopped"
        assert session.state.pid is None

    @pytest.mark.asyncio
    async def test_stop_with_error(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试带错误停止"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )

        await session.stop(error="Connection failed")

        assert session.state.status == "error"
        assert session.state.last_error == "Connection failed"

    def test_touch(self, sample_server: ServerRecord, mock_config: MagicMock) -> None:
        """测试更新最后使用时间"""
        session = Session(
            mcp_id="git_mcp",
            user_id="user123",
            server=sample_server,
            config=mock_config,
        )

        session.touch()

        assert session.state.last_used_at is not None


class TestRuntimeManager:
    """RuntimeManager 测试"""

    @pytest.fixture
    def manager(self) -> RuntimeManager:
        """创建管理器"""
        return RuntimeManager()

    @pytest.fixture
    def sample_server(self) -> ServerRecord:
        """创建示例 ServerRecord"""
        return ServerRecord(
            id="git_mcp",
            name="Git MCP Server",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/git_mcp",
            upstream_key="git_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """创建模拟的 EffectiveConfig"""
        config = MagicMock()
        config.timeouts = Timeouts()
        return config

    @pytest.mark.asyncio
    async def test_create_session(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试创建会话"""
        session = await manager.get_or_create_session(
            server=sample_server,
            config=mock_config,
            user_id="user123",
        )

        assert session is not None
        assert session.mcp_id == "git_mcp"
        assert session.user_id == "user123"

    @pytest.mark.asyncio
    async def test_reuse_session(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试会话复用"""
        # 创建并标记为运行中
        session1 = await manager.get_or_create_session(
            server=sample_server,
            config=mock_config,
            user_id="user123",
        )
        await session1.mark_running(pid=1234)

        # 再次获取应复用
        session2 = await manager.get_or_create_session(
            server=sample_server,
            config=mock_config,
            user_id="user123",
        )

        assert session1 is session2

    @pytest.mark.asyncio
    async def test_get_session(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试获取会话"""
        # 不存在
        session = await manager.get_session("user123", "git_mcp")
        assert session is None

        # 创建后存在
        await manager.get_or_create_session(sample_server, mock_config, "user123")
        session = await manager.get_session("user123", "git_mcp")
        assert session is not None

    @pytest.mark.asyncio
    async def test_remove_session(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试移除会话"""
        await manager.get_or_create_session(sample_server, mock_config, "user123")

        # 移除
        result = await manager.remove_session("user123", "git_mcp")
        assert result is True

        # 再次移除
        result = await manager.remove_session("user123", "git_mcp")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_sessions(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试列出会话"""
        await manager.get_or_create_session(sample_server, mock_config, "user1")
        await manager.get_or_create_session(sample_server, mock_config, "user2")

        # 列出所有
        sessions = await manager.list_sessions()
        assert len(sessions) == 2

        # 按用户筛选
        sessions = await manager.list_sessions(user_id="user1")
        assert len(sessions) == 1
        assert sessions[0].user_id == "user1"

    @pytest.mark.asyncio
    async def test_shutdown(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试关闭所有会话"""
        await manager.get_or_create_session(sample_server, mock_config, "user1")
        await manager.get_or_create_session(sample_server, mock_config, "user2")

        await manager.shutdown()

        sessions = await manager.list_sessions()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        manager: RuntimeManager,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试获取统计信息"""
        session = await manager.get_or_create_session(sample_server, mock_config, "user1")
        await session.mark_running()

        stats = manager.get_stats()

        assert stats["total_sessions"] == 1
        assert stats["running_sessions"] == 1
        assert stats["by_status"]["running"] == 1


class TestSessionRecycler:
    """SessionRecycler 测试"""

    @pytest.fixture
    def manager(self) -> RuntimeManager:
        """创建管理器"""
        return RuntimeManager()

    @pytest.fixture
    def recycler(self, manager: RuntimeManager) -> SessionRecycler:
        """创建回收器"""
        return SessionRecycler(manager, default_idle_ttl=60, check_interval=1)

    @pytest.fixture
    def sample_server(self) -> ServerRecord:
        """创建示例 ServerRecord"""
        return ServerRecord(
            id="git_mcp",
            name="Git MCP Server",
            source=SourceType.RPM,
            install_root="/opt/mcp-servers/servers/git_mcp",
            upstream_key="git_mcp",
            transport=TransportType.STDIO,
            default_config=NormalizedConfig(
                transport=TransportType.STDIO,
                stdio=StdioConfig(command="uv", args=[]),
            ),
        )

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """创建模拟的 EffectiveConfig"""
        config = MagicMock()
        config.timeouts = Timeouts(idle_ttl=60)
        return config

    @pytest.mark.asyncio
    async def test_start_stop(self, recycler: SessionRecycler) -> None:
        """测试启动和停止"""
        await recycler.start()
        assert recycler._running is True  # noqa: SLF001

        await recycler.stop()
        assert recycler._running is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_recycle_idle_session(
        self,
        manager: RuntimeManager,
        recycler: SessionRecycler,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试回收空闲会话"""
        # 创建会话
        session = await manager.get_or_create_session(sample_server, mock_config, "user1")
        await session.mark_running()

        # 模拟空闲超时（设置 last_used_at 为过去时间）
        session.state.last_used_at = datetime.now(UTC) - timedelta(seconds=120)

        # 执行回收
        recycled = await recycler.recycle_now()

        assert recycled == 1
        assert len(await manager.list_sessions()) == 0

    @pytest.mark.asyncio
    async def test_no_recycle_active_session(
        self,
        manager: RuntimeManager,
        recycler: SessionRecycler,
        sample_server: ServerRecord,
        mock_config: MagicMock,
    ) -> None:
        """测试不回收活跃会话"""
        # 创建会话
        session = await manager.get_or_create_session(sample_server, mock_config, "user1")
        await session.mark_running()
        session.touch()  # 刷新使用时间

        # 执行回收
        recycled = await recycler.recycle_now()

        assert recycled == 0
        assert len(await manager.list_sessions()) == 1

    def test_get_stats(self, recycler: SessionRecycler) -> None:
        """测试获取统计信息"""
        stats = recycler.get_stats()

        assert stats["running"] is False
        assert stats["default_idle_ttl"] == 60
        assert stats["check_interval"] == 1
