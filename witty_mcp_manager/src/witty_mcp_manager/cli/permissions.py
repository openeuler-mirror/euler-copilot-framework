"""
CLI permissions module.

Provides permission detection and user identity resolution for CLI commands.

Design:
- root/sudo users: Default to root user's config; can use --global or --user <user_id>
- Regular users: Automatically use current username, cannot use --global

Identity Detection:
- os.getuid() == 0 → root user
- os.getenv("SUDO_USER") → invoked via sudo
- pwd.getpwuid(os.getuid()).pw_name → current user's login name
"""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from enum import Enum


class PrivilegeLevel(Enum):
    """User privilege level."""

    ROOT = "root"
    SUDO = "sudo"
    REGULAR = "regular"


@dataclass
class UserIdentity:
    """
    User identity information.

    Attributes:
        privilege: User's privilege level (root, sudo, or regular)
        effective_uid: Effective user ID (0 for root/sudo)
        real_username: Real username (SUDO_USER for sudo, or current user)
        can_manage_global: Whether user can manage global configuration
        can_manage_others: Whether user can manage other users' configuration

    """

    privilege: PrivilegeLevel
    effective_uid: int
    real_username: str

    @property
    def can_manage_global(self) -> bool:
        """Check if user can manage global configuration."""
        return self.privilege in (PrivilegeLevel.ROOT, PrivilegeLevel.SUDO)

    @property
    def can_manage_others(self) -> bool:
        """Check if user can manage other users' configuration."""
        return self.privilege in (PrivilegeLevel.ROOT, PrivilegeLevel.SUDO)

    @property
    def is_privileged(self) -> bool:
        """Check if user is running with elevated privileges."""
        return self.privilege in (PrivilegeLevel.ROOT, PrivilegeLevel.SUDO)


def get_current_identity() -> UserIdentity:
    """
    Detect current user's identity and privilege level.

    Returns:
        UserIdentity with privilege level and username information.

    Raises:
        OSError: If unable to determine user identity.

    """
    effective_uid = os.getuid()

    # Check if running as root
    if effective_uid == 0:
        # Check if via sudo
        sudo_user = os.getenv("SUDO_USER")
        if sudo_user:
            return UserIdentity(
                privilege=PrivilegeLevel.SUDO,
                effective_uid=effective_uid,
                real_username=sudo_user,
            )
        # Direct root login
        return UserIdentity(
            privilege=PrivilegeLevel.ROOT,
            effective_uid=effective_uid,
            real_username="root",
        )

    # Regular user
    try:
        pw_entry = pwd.getpwuid(effective_uid)
        username = pw_entry.pw_name
    except KeyError as e:
        msg = f"Unable to determine username for uid {effective_uid}"
        raise OSError(msg) from e

    return UserIdentity(
        privilege=PrivilegeLevel.REGULAR,
        effective_uid=effective_uid,
        real_username=username,
    )


@dataclass
class ResolvedScope:
    """
    Resolved scope for CLI operations.

    Attributes:
        is_global: Whether this is a global-level operation
        user_id: User ID for user-level operations (None for global)

    """

    is_global: bool
    user_id: str | None

    @property
    def scope_name(self) -> str:
        """Get human-readable scope name."""
        if self.is_global:
            return "global"
        return f"user/{self.user_id}"


class CliPermissionError(Exception):
    """Permission-related errors for CLI operations."""

    def __init__(self, message: str, suggestion: str | None = None) -> None:
        """Initialize permission error."""
        super().__init__(message)
        self.suggestion = suggestion


# Alias for backward compatibility (import as CliPermissionError is preferred)
PermissionError = CliPermissionError  # noqa: A001


def resolve_scope(
    identity: UserIdentity,
    *,
    global_flag: bool,
    user_flag: str | None,
    operation: str = "operation",
) -> ResolvedScope:
    """
    Resolve the target scope based on user identity and flags.

    Args:
        identity: Current user's identity
        global_flag: Whether --global flag was specified
        user_flag: Value of --user flag (if any)
        operation: Operation name for error messages

    Returns:
        ResolvedScope with target scope information

    Raises:
        PermissionError: If user lacks permission or invalid flag combination

    """
    # Check for conflicting flags
    if global_flag and user_flag:
        msg = "Cannot specify both --global and --user."
        raise CliPermissionError(
            msg,
            suggestion="Use --global for system-level or --user <user_id> for user-level.",
        )

    # Privileged user (root/sudo)
    if identity.is_privileged:
        if global_flag:
            return ResolvedScope(is_global=True, user_id=None)

        if user_flag:
            return ResolvedScope(is_global=False, user_id=user_flag)

        # Default: root/sudo without flags -> use "root" user's config
        # This ensures `sudo witty-mcp ...` works as expected
        return ResolvedScope(is_global=False, user_id="root")

    # Regular user
    if global_flag:
        msg = "--global requires root/sudo privileges."
        raise CliPermissionError(
            msg,
            suggestion=f"Run with sudo: sudo witty-mcp {operation} --global",
        )

    if user_flag and user_flag != identity.real_username:
        msg = f"Cannot manage other user's configuration ('{user_flag}')."
        raise CliPermissionError(
            msg,
            suggestion=f"You can only manage your own configuration: --user {identity.real_username}",
        )

    # Regular user: auto-resolve to current user
    return ResolvedScope(is_global=False, user_id=identity.real_username)


def resolve_user_for_ipc(
    identity: UserIdentity,
    *,
    user_flag: str | None,
    operation: str = "operation",  # noqa: ARG001 - kept for API consistency
) -> str:
    """
    Resolve user ID for IPC operations (daemon required).

    For IPC operations, we always need a user_id for the X-Witty-User header.
    This function resolves it based on identity and flags.

    Args:
        identity: Current user's identity
        user_flag: Value of --user flag (if any)
        operation: Operation name for error messages (reserved for future use)

    Returns:
        User ID string for IPC

    Raises:
        PermissionError: If user lacks permission

    """
    # Privileged user (root/sudo)
    if identity.is_privileged:
        # Default to "root" if no user specified
        return user_flag if user_flag else "root"

    # Regular user
    if user_flag and user_flag != identity.real_username:
        msg = f"Cannot access other user's data ('{user_flag}')."
        raise CliPermissionError(
            msg,
            suggestion="You can only access your own data.",
        )

    # Auto-resolve to current user
    return identity.real_username
