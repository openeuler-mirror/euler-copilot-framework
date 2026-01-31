"""
TTL 回收模块

负责清理空闲超时的 MCP 会话，释放系统资源。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from witty_mcp_manager.runtime.manager import RuntimeManager

logger = logging.getLogger(__name__)


class SessionRecycler:
    """
    会话回收器

    定期检查并回收超过 idle_ttl 的空闲会话
    """

    DEFAULT_IDLE_TTL = 600  # 默认空闲 TTL（10 分钟）
    CHECK_INTERVAL = 60  # 检查间隔（1 分钟）

    def __init__(
        self,
        runtime_manager: "RuntimeManager",
        default_idle_ttl: int = DEFAULT_IDLE_TTL,
        check_interval: int = CHECK_INTERVAL,
    ) -> None:
        """
        初始化回收器

        Args:
            runtime_manager: Runtime 管理器
            default_idle_ttl: 默认空闲 TTL（秒）
            check_interval: 检查间隔（秒）
        """
        self.runtime_manager = runtime_manager
        self.default_idle_ttl = default_idle_ttl
        self.check_interval = check_interval

        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """启动回收器"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Session recycler started (idle_ttl=%ds, interval=%ds)",
            self.default_idle_ttl,
            self.check_interval,
        )

    async def stop(self) -> None:
        """停止回收器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Session recycler stopped")

    async def _run_loop(self) -> None:
        """回收循环"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._recycle_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in recycler loop: %s", e)

    async def _recycle_idle_sessions(self) -> None:
        """回收空闲会话"""
        now = datetime.now(timezone.utc)
        recycled = 0

        sessions = await self.runtime_manager.list_sessions()
        for session in sessions:
            if not session.is_running:
                continue

            # 获取会话的 idle_ttl（优先使用配置值）
            idle_ttl = self.default_idle_ttl
            if session.config and session.config.timeouts:
                idle_ttl = session.config.timeouts.idle_ttl

            # 检查是否超时
            last_used = session.state.last_used_at
            if last_used is None:
                continue

            idle_seconds = (now - last_used).total_seconds()
            if idle_seconds >= idle_ttl:
                logger.info(
                    "Recycling idle session: %s (idle=%.0fs, ttl=%ds)",
                    session.session_key,
                    idle_seconds,
                    idle_ttl,
                )
                await self.runtime_manager.remove_session(
                    session.user_id,
                    session.mcp_id,
                )
                recycled += 1

        if recycled > 0:
            logger.info("Recycled %d idle session(s)", recycled)

    async def recycle_now(self) -> int:
        """
        立即执行回收

        Returns:
            回收的会话数量
        """
        before = len(await self.runtime_manager.list_sessions())
        await self._recycle_idle_sessions()
        after = len(await self.runtime_manager.list_sessions())
        return before - after

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "running": self._running,
            "default_idle_ttl": self.default_idle_ttl,
            "check_interval": self.check_interval,
        }
