"""Tests for CLI template renderer."""

from __future__ import annotations

import pytest
from jinja2.exceptions import TemplateNotFound
from rich.console import Console

from witty_mcp_manager.cli.renderer import (
    print_template,
    render_template,
)


def test_render_daemon_status() -> None:
    """Test rendering daemon status template."""
    context = {
        "active_sessions": 3,
        "total_servers": 10,
        "enabled_servers": 8,
        "uptime": 3600,
        "version": "1.0.0",
    }
    result = render_template("daemon_status.txt", context)
    assert "Witty MCP Manager Status" in result
    assert "Active Sessions:[/bold] 3" in result
    assert "Discovered Servers:[/bold] 10" in result
    assert "Enabled Servers:[/bold] 8" in result
    assert "Uptime (s):[/bold] 3600" in result
    assert "Version:[/bold] 1.0.0" in result


def test_render_session_status() -> None:
    """Test rendering session status template."""
    context = {
        "mcp_id": "test_server",
        "user_id": "user123",
        "status": "running",
        "pid": "12345",
        "started_at": "2024-01-01T00:00:00",
        "last_used_at": "2024-01-01T01:00:00",
        "idle_time_sec": 3600,
        "restart_count": "0",
        "error_count": "0",
        "last_error": "N/A",
    }
    result = render_template("session_status.txt", context)
    assert "Server: test_server" in result
    assert "User:[/bold] user123" in result
    assert "Status:[/bold] running" in result
    assert "PID:[/bold] 12345" in result
    assert "1h 0m 0s" in result or "3600s" in result


def test_render_config_status() -> None:
    """Test rendering config status template."""
    context = {
        "scan_paths": "/path1, /path2",
        "socket_path": "/run/witty/mcp-manager.sock",
        "idle_session_ttl": 300,
        "command_allowlist": "python, node, npx",
    }
    result = render_template("config_status.txt", context)
    assert "Witty MCP Manager Configuration" in result
    assert "Scan Paths:[/bold] /path1, /path2" in result
    assert "Socket Path:[/bold] /run/witty/mcp-manager.sock" in result
    assert "Idle Session TTL:[/bold] 300s" in result
    assert "Command Allowlist:[/bold] python, node, npx" in result


def test_render_error_user_required() -> None:
    """Test rendering error when user ID is required."""
    context = {"command": "status <mcp_id>"}
    result = render_template("error_user_required.txt", context)
    assert "Error: --user <user_id> is required for status <mcp_id>" in result
    assert "System username is NOT used as user ID" in result


def test_render_error_daemon_connect() -> None:
    """Test rendering daemon connection error."""
    result = render_template("error_daemon_connect.txt", {})
    assert "Cannot connect to witty-mcp-manager daemon" in result
    assert "systemctl status witty-mcp-manager" in result


def test_render_error_http() -> None:
    """Test rendering HTTP error."""
    context = {
        "status_code": 404,
        "response_text": "Not Found",
    }
    result = render_template("error_http.txt", context)
    assert "HTTP error 404: Not Found" in result


def test_render_error_permission() -> None:
    """Test rendering permission error."""
    context = {
        "error": "Permission denied",
        "suggestion": "Try using sudo",
    }
    result = render_template("error_permission.txt", context)
    assert "Error: Permission denied" in result
    assert "Try using sudo" in result


def test_render_no_sessions() -> None:
    """Test rendering no active sessions message."""
    result = render_template("info_no_sessions.txt", {})
    assert "No active sessions" in result


def test_render_no_servers() -> None:
    """Test rendering no servers found message."""
    result = render_template("info_no_servers.txt", {})
    assert "No servers found" in result


def test_format_duration_filter() -> None:
    """Test duration formatting filter."""
    # Test hours, minutes, seconds
    result = render_template(
        "session_status.txt",
        {
            "mcp_id": "test",
            "user_id": "user",
            "status": "running",
            "pid": "123",
            "started_at": "now",
            "last_used_at": "now",
            "idle_time_sec": 3665,
            "restart_count": "0",
            "error_count": "0",
            "last_error": "N/A",
        },
    )
    assert "1h 1m 5s" in result

    # Test minutes only
    result_min = render_template(
        "session_status.txt",
        {
            "mcp_id": "test",
            "user_id": "user",
            "status": "running",
            "pid": "123",
            "started_at": "now",
            "last_used_at": "now",
            "idle_time_sec": 65,
            "restart_count": "0",
            "error_count": "0",
            "last_error": "N/A",
        },
    )
    assert "1m 5s" in result_min

    # Test None value
    result_none = render_template(
        "session_status.txt",
        {
            "mcp_id": "test",
            "user_id": "user",
            "status": "running",
            "pid": "123",
            "started_at": "now",
            "last_used_at": "now",
            "idle_time_sec": None,
            "restart_count": "0",
            "error_count": "0",
            "last_error": "N/A",
        },
    )
    assert "N/A" in result_none


def test_print_template(capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_template function."""
    console = Console()
    print_template(
        console,
        "error_http.txt",
        {"status_code": 500, "response_text": "Internal Error"},
    )
    captured = capsys.readouterr()
    # Note: Rich console may add ANSI codes, just check content
    assert "500" in captured.out or "Internal Error" in captured.out


def test_template_not_found() -> None:
    """Test error when template doesn't exist."""
    with pytest.raises(TemplateNotFound):
        render_template("nonexistent_template.txt", {})
