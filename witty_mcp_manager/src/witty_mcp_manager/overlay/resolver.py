"""
Overlay 配置解析模块

负责合并多层配置（default → global → user），生成最终生效配置。
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from witty_mcp_manager.overlay.storage import OverlayStorage
from witty_mcp_manager.registry.models import (
    Concurrency,
    NormalizedConfig,
    Override,
    ServerRecord,
    SseConfig,
    StdioConfig,
    Timeouts,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class EffectiveConfig:
    """
    最终生效配置

    合并 default_config + global_override + user_override 后的结果
    """

    mcp_id: str
    user_id: str | None
    disabled: bool
    config: NormalizedConfig
    timeouts: Timeouts
    concurrency: Concurrency
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_enabled(self) -> bool:
        """是否启用"""
        return not self.disabled


class OverlayResolver:
    """
    Overlay 配置解析器

    合并优先级（从低到高）：
    1. ServerRecord.default_config（默认配置）
    2. Global Override（全局覆盖）
    3. User Override（用户覆盖）
    """

    def __init__(self, storage: OverlayStorage) -> None:
        """
        初始化解析器

        Args:
            storage: Overlay 存储实例
        """
        self.storage = storage

    def resolve(
        self,
        server: ServerRecord,
        user_id: str | None = None,
    ) -> EffectiveConfig:
        """
        解析最终生效配置

        Args:
            server: MCP Server 记录
            user_id: 用户 ID（None 表示仅应用全局配置）

        Returns:
            最终生效配置
        """
        # 1. 从默认配置开始
        config = copy.deepcopy(server.default_config)
        timeouts = copy.deepcopy(config.timeouts)
        concurrency = Concurrency()
        env: dict[str, str] = {}
        headers: dict[str, str] = {}
        disabled = server.default_disabled

        # 复制默认环境变量
        if config.stdio:
            env.update(config.stdio.env)
        if config.sse:
            headers.update(config.sse.headers)

        # 2. 应用全局覆盖
        global_override = self.storage.load_override(server.id)
        if global_override:
            disabled, config, timeouts, concurrency, env, headers = self._apply_override(
                global_override, disabled, config, timeouts, concurrency, env, headers
            )
            logger.debug("Applied global override for %s", server.id)

        # 3. 应用用户覆盖
        if user_id:
            user_override = self.storage.load_override(server.id, user_id)
            if user_override:
                disabled, config, timeouts, concurrency, env, headers = self._apply_override(
                    user_override, disabled, config, timeouts, concurrency, env, headers
                )
                logger.debug("Applied user override for %s (user=%s)", server.id, user_id)

        return EffectiveConfig(
            mcp_id=server.id,
            user_id=user_id,
            disabled=disabled,
            config=config,
            timeouts=timeouts,
            concurrency=concurrency,
            env=env,
            headers=headers,
        )

    def _apply_override(
        self,
        override: Override,
        disabled: bool,
        config: NormalizedConfig,
        timeouts: Timeouts,
        concurrency: Concurrency,
        env: dict[str, str],
        headers: dict[str, str],
    ) -> tuple[bool, NormalizedConfig, Timeouts, Concurrency, dict[str, str], dict[str, str]]:
        """
        应用覆盖配置

        Args:
            override: 覆盖配置
            disabled: 当前禁用状态
            config: 当前配置
            timeouts: 当前超时配置
            concurrency: 当前并发配置
            env: 当前环境变量
            headers: 当前请求头

        Returns:
            更新后的配置元组
        """
        # 禁用状态
        if override.disabled is not None:
            disabled = override.disabled

        # 环境变量（合并）
        if override.env:
            env.update(override.env)

        # 请求头（合并）
        if override.headers:
            headers.update(override.headers)

        # 超时配置（覆盖）
        if override.timeouts:
            timeouts = override.timeouts

        # 并发配置（覆盖）
        if override.concurrency:
            concurrency = override.concurrency

        # 应用参数补丁（arg_patches）
        config = self._apply_arg_patches(config, override.arg_patches)

        return disabled, config, timeouts, concurrency, env, headers

    def _apply_arg_patches(
        self,
        config: NormalizedConfig,
        arg_patches: list[dict],
    ) -> NormalizedConfig:
        """
        应用参数补丁

        支持的操作：
        - {"op": "add", "value": "arg"} - 添加参数
        - {"op": "remove", "value": "arg"} - 移除参数
        - {"op": "replace", "old": "old_arg", "new": "new_arg"} - 替换参数

        Args:
            config: 当前配置
            arg_patches: 参数补丁列表

        Returns:
            更新后的配置
        """
        if not arg_patches or not config.stdio:
            return config

        args = list(config.stdio.args)

        for patch in arg_patches:
            op = patch.get("op")
            if op == "add":
                value = patch.get("value")
                if value and value not in args:
                    args.append(value)
            elif op == "remove":
                value = patch.get("value")
                if value and value in args:
                    args.remove(value)
            elif op == "replace":
                old = patch.get("old")
                new = patch.get("new")
                if old and new and old in args:
                    idx = args.index(old)
                    args[idx] = new

        # 更新 stdio 配置
        config.stdio = StdioConfig(
            command=config.stdio.command,
            args=args,
            env=config.stdio.env,
            cwd=config.stdio.cwd,
        )

        return config

    def is_enabled_for_user(self, server: ServerRecord, user_id: str) -> bool:
        """
        检查 MCP 对用户是否启用

        优先级：用户设置 > 全局设置 > 默认设置

        Args:
            server: MCP Server 记录
            user_id: 用户 ID

        Returns:
            是否启用
        """
        # 检查用户设置
        user_enabled = self.storage.is_user_enabled(server.id, user_id)
        if user_enabled is not None:
            return user_enabled

        # 检查全局设置
        if self.storage.is_globally_disabled(server.id):
            return False

        # 返回默认设置
        return not server.default_disabled

    def get_enabled_servers(
        self,
        servers: list[ServerRecord],
        user_id: str | None = None,
    ) -> list[ServerRecord]:
        """
        获取启用的 MCP Server 列表

        Args:
            servers: 所有 MCP Server 记录
            user_id: 用户 ID（用于过滤用户启用的 MCP）

        Returns:
            启用的 MCP Server 列表（系统级未禁用的）
        """
        result = []
        for server in servers:
            # 系统级检查：全局禁用的不返回
            if self.storage.is_globally_disabled(server.id):
                continue
            # 默认禁用但未全局启用的不返回
            if server.default_disabled:
                global_override = self.storage.load_override(server.id)
                if not global_override or global_override.disabled is not False:
                    continue
            result.append(server)
        return result
