"""
Runtime subcommand - inspect runtime state.

Commands:
- status: Show overall daemon status
- sessions: List active sessions
- kill: Terminate a session
"""

from __future__ import annotations

import getpass
import json
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from witty_mcp_manager.ipc.auth import HEADER_USER_ID

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


def _resolve_user_id(user_id: str | None) -> str:
    """Resolve user ID for IPC calls."""
    return user_id or getpass.getuser()


@app.command("status")
def status(
    mcp_id: Annotated[
        str | None,
        typer.Argument(help="MCP Server ID"),
    ] = None,
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show overall daemon status."""
    try:
        resolved_user = _resolve_user_id(user_id)
        with _get_client(resolved_user) as client:
            if mcp_id:
                response = client.get(f"/v1/runtime/sessions/{mcp_id}")
                response.raise_for_status()
                session_data = response.json().get("data", {})
                data = {"session": session_data}
            else:
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
                data = {
                    "active_sessions": active_sessions,
                    "total_servers": len(servers),
                    "enabled_servers": enabled_servers,
                    "uptime": health.get("uptime_sec", 0),
                    "version": health.get("version", ""),
                }

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        if mcp_id:
            session = data.get("session", {})
            console.print(f"\n[bold cyan]Session Status: {mcp_id}[/bold cyan]\n")
            console.print(f"[bold]User:[/bold] {session.get('user_id', 'N/A')}")
            console.print(f"[bold]Status:[/bold] {session.get('status', 'N/A')}")
            console.print(f"[bold]PID:[/bold] {session.get('pid', 'N/A')}")
            console.print(f"[bold]Started At:[/bold] {session.get('started_at', 'N/A')}")
            console.print(f"[bold]Last Used:[/bold] {session.get('last_used_at', 'N/A')}")
            console.print(f"[bold]Idle (s):[/bold] {session.get('idle_time_sec', 'N/A')}")
            console.print(f"[bold]Restart Count:[/bold] {session.get('restart_count', 'N/A')}")
            console.print(f"[bold]Last Error:[/bold] {session.get('last_error', 'N/A')}")
        else:
            console.print("\n[bold cyan]Witty MCP Manager Status[/bold cyan]\n")
            console.print(f"[bold]Active Sessions:[/bold] {data.get('active_sessions', 0)}")
            console.print(f"[bold]Discovered Servers:[/bold] {data.get('total_servers', 0)}")
            console.print(f"[bold]Enabled Servers:[/bold] {data.get('enabled_servers', 0)}")
            console.print(f"[bold]Uptime (s):[/bold] {data.get('uptime', 'N/A')}")
            console.print(f"[bold]Version:[/bold] {data.get('version', 'N/A')}")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        console.print("[yellow]Is the daemon running? Try: systemctl status witty-mcp-manager[/yellow]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("sessions")
def list_sessions(
    all_users: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--all-users", help="List sessions for all users"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List active MCP sessions."""
    try:
        resolved_user = _resolve_user_id(user_id)
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
            console.print("[yellow]No active sessions.[/yellow]")
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
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
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
    """Terminate a session."""
    try:
        _ = force
        console.print(
            "[yellow]Not supported:[/yellow] IPC API does not expose session termination. "
            "Disable the server for a user instead."
        )
        raise typer.Exit(code=2)

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Session '{session_key}' not found.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None
