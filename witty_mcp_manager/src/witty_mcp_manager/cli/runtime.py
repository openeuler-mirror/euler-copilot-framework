"""
Runtime subcommand - inspect runtime state.

Commands:
- status: Show overall daemon status
- sessions: List active sessions
- kill: Terminate a session

Note: This is an admin CLI. For user-specific operations (e.g., viewing a
specific user's session), you must explicitly specify --user <user_id>.
The system username is NOT automatically used as the user ID because
system username ≠ business user ID (which could be OIDC sub, email, UUID, etc.).
"""

from __future__ import annotations

import json
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from witty_mcp_manager.ipc.auth import HEADER_USER_ID, SYSTEM_USER_ID

from .renderer import print_template

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Inspect runtime state")


def _get_client(user_id: str) -> httpx.Client:
    """Create HTTP client for UDS communication."""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
        headers={HEADER_USER_ID: user_id},
    )


def _require_user_id(user_id: str | None, command: str) -> str:
    """Require explicit user_id for user-level operations."""
    if not user_id:
        print_template(console, "error_user_required.txt", {"command": command})
        raise typer.Exit(code=1)
    return user_id


def _fetch_session_data(client: httpx.Client, mcp_id: str) -> dict[str, object]:
    """Fetch session data for a specific MCP server."""
    response = client.get(f"/v1/runtime/sessions/{mcp_id}")
    response.raise_for_status()
    return {"session": response.json().get("data", {})}


def _fetch_daemon_status(client: httpx.Client) -> dict[str, object]:
    """Fetch overall daemon status."""
    health_resp = client.get("/health")
    health_resp.raise_for_status()
    health = health_resp.json().get("data", {})

    servers_resp = client.get("/v1/servers", params={"include_disabled": "true"})
    servers_resp.raise_for_status()
    servers = servers_resp.json().get("data", [])

    sessions_resp = client.get("/v1/runtime/sessions")
    sessions_resp.raise_for_status()
    sessions = sessions_resp.json().get("data", [])

    active_sessions = len([s for s in sessions if s.get("status") == "running"])
    enabled_servers = len([s for s in servers if s.get("user_enabled")])
    return {
        "active_sessions": active_sessions,
        "total_servers": len(servers),
        "enabled_servers": enabled_servers,
        "uptime": health.get("uptime_sec", 0),
        "version": health.get("version", ""),
    }


def _print_session_status(mcp_id: str, data: dict[str, object]) -> None:
    """Print session status to console."""
    session = data.get("session", {})
    if isinstance(session, dict):
        context = {
            "mcp_id": mcp_id,
            "user_id": session.get("user_id", "N/A"),
            "status": session.get("status", "N/A"),
            "pid": session.get("pid", "N/A"),
            "started_at": session.get("started_at", "N/A"),
            "last_used_at": session.get("last_used_at", "N/A"),
            "idle_time_sec": session.get("idle_time_sec"),
            "restart_count": session.get("restart_count", "N/A"),
            "error_count": session.get("error_count", "N/A"),
            "last_error": session.get("last_error", "N/A"),
        }
        print_template(console, "session_status.txt", context)


def _print_daemon_status(data: dict[str, object]) -> None:
    """Print daemon status to console."""
    context = {
        "active_sessions": data.get("active_sessions", 0),
        "total_servers": data.get("total_servers", 0),
        "enabled_servers": data.get("enabled_servers", 0),
        "uptime": data.get("uptime", "N/A"),
        "version": data.get("version", "N/A"),
    }
    print_template(console, "daemon_status.txt", context)


@app.command("status")
def status(
    mcp_id: Annotated[
        str | None,
        typer.Argument(help="MCP Server ID (requires --user when specified)"),
    ] = None,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID for user-specific session query"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """
    Show overall daemon status or a specific session.

    Without mcp_id: Shows daemon status (uses __system__ context).
    With mcp_id: Shows user session status (requires --user).

    Examples:
        witty-mcp runtime status                    # Daemon status
        witty-mcp runtime status git_mcp --user u1  # User session

    """
    try:
        if mcp_id:
            resolved_user = _require_user_id(user_id, "status <mcp_id>")
            with _get_client(resolved_user) as client:
                data = _fetch_session_data(client, mcp_id)
        else:
            with _get_client(SYSTEM_USER_ID) as client:
                data = _fetch_daemon_status(client)

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        if mcp_id:
            _print_session_status(mcp_id, data)
        else:
            _print_daemon_status(data)

    except httpx.ConnectError:
        print_template(console, "error_daemon_connect.txt", {})
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        print_template(
            console,
            "error_http.txt",
            {
                "status_code": e.response.status_code,
                "response_text": e.response.text,
            },
        )
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("sessions")
def list_sessions(
    all_users: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--all-users", help="List sessions for all users (admin view)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID to filter sessions"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """
    List active MCP sessions.

    By default, requires --user to specify which user's sessions to list.
    Use --all-users to list sessions for all users (admin operation).

    Examples:
        witty-mcp runtime sessions --user user123
        witty-mcp runtime sessions --all-users

    """
    try:
        # Use SYSTEM_USER_ID for admin view (--all-users), otherwise require explicit user
        resolved_user = SYSTEM_USER_ID if all_users else _require_user_id(user_id, "sessions")

        with _get_client(resolved_user) as client:
            response = client.get(
                "/v1/runtime/sessions",
                params={"all_users": str(all_users).lower()},
            )
            response.raise_for_status()
            data = response.json()

        sessions = data.get("data", [])

        if json_output:
            console.print_json(json.dumps({"sessions": sessions}, indent=2))
            return

        if not sessions:
            print_template(console, "info_no_sessions.txt", {})
            return

        table = Table(title="Active MCP Sessions")
        table.add_column("Server ID", style="magenta")
        table.add_column("User", style="blue")
        table.add_column("Status")
        table.add_column("PID")
        table.add_column("Idle (s)")

        for session in sessions:
            table.add_row(
                session.get("mcp_id", ""),
                session.get("user_id", ""),
                session.get("status", ""),
                str(session.get("pid", "")),
                str(session.get("idle_time_sec", "")),
            )

        console.print(table)

    except httpx.ConnectError:
        print_template(console, "error_daemon_connect.txt", {})
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        print_template(
            console,
            "error_http.txt",
            {
                "status_code": e.response.status_code,
                "response_text": e.response.text,
            },
        )
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("kill")
def kill_session(
    session_key: Annotated[str, typer.Argument(help="Session key to terminate")],
    force: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--force", "-f", help="Force kill without graceful shutdown"),
    ] = False,
) -> None:
    """Terminate a session (not currently supported)."""
    _ = force
    _ = session_key
    console.print(
        "[yellow]Not supported:[/yellow] IPC API does not expose session termination. "
        "Disable the server for a user instead.",
    )
    raise typer.Exit(code=2)
