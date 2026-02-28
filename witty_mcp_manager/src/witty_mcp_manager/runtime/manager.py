"""
Runtime 会话管理模块

负责管理 MCP 会话的生命周期，支持 per (user_id, mcp_id) 的会话复用。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from witty_mcp_manager.exceptions import WittyRuntimeError
from witty_mcp_manager.registry.models import RuntimeState, RuntimeStatus, ServerRecord

if TYPE_CHECKING:
    from witty_mcp_manager.overlay.resolver import EffectiveConfig

logger = logging.getLogger(__name__)


class Session:
    """
    MCP 会话

    封装与单个 MCP Server 的连接/进程
    """

    def __init__(
        self,
        mcp_id: str,
        user_id: str,
        server: ServerRecord,
        config: EffectiveConfig,
    ) -> None:
        """
        初始化会话

        Args:
            mcp_id: MCP Server ID
            user_id: 用户 ID
            server: MCP Server 记录
            config: 最终生效配置

        """
        self.mcp_id = mcp_id
        self.user_id = user_id
        self.server = server
        self.config = config

        # 状态
        self.state = RuntimeState(
            user_id=user_id,
            mcp_id=mcp_id,
            status=RuntimeStatus.STOPPED,
        )

        # 内部状态
        self._client: Any = None  # MCP Client 实例（由 Adapter 设置）
        self._process: asyncio.subprocess.Process | None = None  # STDIO 子进程
        self._lock = asyncio.Lock()

    @property
    def session_key(self) -> str:
        """会话唯一键"""
        return f"{self.user_id}:{self.mcp_id}"

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.state.status == RuntimeStatus.RUNNING

    def touch(self) -> None:
        """更新最后使用时间"""
        self.state.last_used_at = datetime.now(UTC)

    async def start(self) -> None:
        """
        启动会话

        注意：实际启动逻辑由 Adapter 实现，此方法仅更新状态
        """
        async with self._lock:
            self.state.status = RuntimeStatus.STARTING
            self.state.started_at = datetime.now(UTC)
            self.state.last_used_at = self.state.started_at
            logger.info("Session starting: %s", self.session_key)

    async def mark_running(self, pid: int | None = None) -> None:
        """
        标记为运行中

        Args:
            pid: 进程 ID（仅 STDIO）

        """
        async with self._lock:
            self.state.status = RuntimeStatus.RUNNING
            self.state.pid = pid
            logger.info("Session running: %s (pid=%s)", self.session_key, pid)

    async def stop(self, error: str | None = None) -> None:
        """
        停止会话

        Args:
            error: 错误信息（如有）

        """
        async with self._lock:
            if error:
                self.state.status = RuntimeStatus.ERROR
                self.state.last_error = error
                logger.warning("Session error: %s - %s", self.session_key, error)
            else:
                self.state.status = RuntimeStatus.STOPPED
                logger.info("Session stopped: %s", self.session_key)

            # 清理进程
            if self._process:
                try:
                    self._process.terminate()
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except TimeoutError:
                    self._process.kill()
                except ProcessLookupError as e:
                    logger.warning("Failed to terminate process: %s", e)
                finally:
                    self._process = None

            self.state.pid = None

    async def restart(self) -> None:
        """重启会话"""
        self.state.restart_count += 1
        await self.stop()
        await self.start()


class RuntimeManager:
    """
    Runtime 管理器

    管理所有 MCP 会话，支持 per (user_id, mcp_id) 的会话复用
    """

    MAX_RESTART_COUNT = 3  # 最大重启次数

    def __init__(self) -> None:
        """初始化管理器"""
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, user_id: str, mcp_id: str) -> str:
        """生成会话键"""
        return f"{user_id}:{mcp_id}"

    async def get_or_create_session(
        self,
        server: ServerRecord,
        config: EffectiveConfig,
        user_id: str,
    ) -> Session:
        """
        获取或创建会话

        Args:
            server: MCP Server 记录
            config: 最终生效配置
            user_id: 用户 ID

        Returns:
            会话实例

        Raises:
            WittyRuntimeError: 创建失败

        """
        key = self._make_key(user_id, server.id)

        async with self._lock:
            # 尝试复用现有会话
            if key in self._sessions:
                session = self._sessions[key]
                if session.is_running:
                    session.touch()
                    logger.debug("Reusing session: %s", key)
                    return session
                # 会话存在但未运行，检查重启次数
                if session.state.restart_count >= self.MAX_RESTART_COUNT:
                    msg = f"Session {key} exceeded max restart count ({self.MAX_RESTART_COUNT})"
                    raise WittyRuntimeError(msg)

            # 创建新会话
            session = Session(
                mcp_id=server.id,
                user_id=user_id,
                server=server,
                config=config,
            )
            self._sessions[key] = session
            logger.info("Created session: %s", key)

        return session

    async def get_session(self, user_id: str, mcp_id: str) -> Session | None:
        """
        获取会话

        Args:
            user_id: 用户 ID
            mcp_id: MCP Server ID

        Returns:
            会话实例，不存在则返回 None

        """
        key = self._make_key(user_id, mcp_id)
        return self._sessions.get(key)

    async def remove_session(self, user_id: str, mcp_id: str) -> bool:
        """
        移除会话

        Args:
            user_id: 用户 ID
            mcp_id: MCP Server ID

        Returns:
            是否移除成功

        """
        key = self._make_key(user_id, mcp_id)

        async with self._lock:
            if key not in self._sessions:
                return False

            session = self._sessions.pop(key)
            await session.stop()
            logger.info("Removed session: %s", key)
            return True

    async def list_sessions(self, user_id: str | None = None) -> list[Session]:
        """
        列出会话

        Args:
            user_id: 用户 ID（None 表示所有用户）

        Returns:
            会话列表

        """
        if user_id:
            return [s for s in self._sessions.values() if s.user_id == user_id]
        return list(self._sessions.values())

    async def list_sessions_for_mcp(self, mcp_id: str) -> list[Session]:
        """
        列出 MCP 的所有会话

        Args:
            mcp_id: MCP Server ID

        Returns:
            会话列表

        """
        return [s for s in self._sessions.values() if s.mcp_id == mcp_id]

    async def get_runtime_state(self, user_id: str, mcp_id: str) -> RuntimeState | None:
        """
        获取运行时状态

        Args:
            user_id: 用户 ID
            mcp_id: MCP Server ID

        Returns:
            运行时状态，不存在则返回 None

        """
        session = await self.get_session(user_id, mcp_id)
        return session.state if session else None

    async def shutdown(self) -> None:
        """关闭所有会话"""
        async with self._lock:
            for session in self._sessions.values():
                await session.stop()
            self._sessions.clear()
            logger.info("All sessions shutdown")

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典

        """
        total = len(self._sessions)
        running = sum(1 for s in self._sessions.values() if s.is_running)
        by_status: dict[str, int] = {}
        for s in self._sessions.values():
            status = s.state.status
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_sessions": total,
            "running_sessions": running,
            "by_status": by_status,
        }
