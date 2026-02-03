"""
Runtime subcommand - inspect runtime state.

Commands:
- status: Show overall daemon status
- sessions: List active sessions
- kill: Terminate a session
"""

from __future__ import annotations

import json
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Inspect runtime state")


def _get_client() -> httpx.Client:
    """Create HTTP client for UDS communication."""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
    )


@app.command("status")
def status(
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show overall daemon status."""
    try:
        with _get_client() as client:
            response = client.get("/v1/runtime/status")
            response.raise_for_status()
            data = response.json()

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        console.print("\n[bold cyan]Witty MCP Manager Status[/bold cyan]\n")
        console.print(f"[bold]Active Sessions:[/bold] {data.get('active_sessions', 0)}")
        console.print(f"[bold]Discovered Servers:[/bold] {data.get('total_servers', 0)}")
        console.print(f"[bold]Enabled Servers:[/bold] {data.get('enabled_servers', 0)}")
        console.print(f"[bold]Uptime:[/bold] {data.get('uptime', 'N/A')}")

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
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List active MCP sessions."""
    try:
        with _get_client() as client:
            response = client.get("/v1/runtime/sessions")
            response.raise_for_status()
            data = response.json()

        sessions = data.get("sessions", [])

        if json_output:
            console.print_json(json.dumps({"sessions": sessions}, indent=2))
            return

        if not sessions:
            console.print("[yellow]No active sessions.[/yellow]")
            return

        table = Table(title="Active MCP Sessions")
        table.add_column("Session Key", style="cyan")
        table.add_column("Server ID", style="magenta")
        table.add_column("User", style="blue")
        table.add_column("Uptime")
        table.add_column("Last Used")

        for session in sessions:
            table.add_row(
                session.get("session_key", "")[:16] + "...",
                session.get("server_id", ""),
                session.get("user", ""),
                session.get("uptime", "N/A"),
                session.get("last_used", "N/A"),
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
        with _get_client() as client:
            response = client.delete(
                f"/v1/runtime/sessions/{session_key}",
                params={"force": str(force).lower()},
            )
            response.raise_for_status()

        console.print(f"[green]✓[/green] Session '{session_key}' terminated.")

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
