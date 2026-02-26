"""
Servers subcommand - manage MCP servers.

Commands:
- list: List all discovered servers
- enable: Enable a server
- disable: Disable a server
- info: Show detailed information about a server
- tools: List tools provided by a server
"""

from __future__ import annotations

import getpass
import json
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from witty_mcp_manager.ipc.auth import HEADER_USER_ID, SYSTEM_USER_ID

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Manage MCP servers")


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


def _resolve_system_user_id(user_id: str | None) -> str:
    """Resolve system user ID for global operations."""
    return user_id or SYSTEM_USER_ID


@app.command("list")
def list_servers(
    enabled_only: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--enabled", help="Show only enabled servers"),
    ] = False,
    include_disabled: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--all", help="Include system-disabled servers"),
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
    """List all discovered MCP servers."""
    try:
        resolved_user = _resolve_user_id(user_id)
        with _get_client(resolved_user) as client:
            response = client.get(
                "/v1/servers",
                params={"include_disabled": str(include_disabled).lower()},
            )
            response.raise_for_status()
            data = response.json()

        servers = data.get("data", [])
        if enabled_only:
            servers = [s for s in servers if s.get("user_enabled", False)]

        if json_output:
            console.print_json(json.dumps({"servers": servers}, indent=2))
            return

        if not servers:
            console.print("[yellow]No servers found.[/yellow]")
            return

        table = Table(title="MCP Servers")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Source", style="blue")
        table.add_column("Status", style="green")
        table.add_column("User Enabled", style="green")
        table.add_column("Summary")

        for server in servers:
            table.add_row(
                server.get("mcp_id", ""),
                server.get("name", ""),
                server.get("source", ""),
                server.get("status", ""),
                "✓" if server.get("user_enabled", False) else "✗",
                server.get("summary", ""),
            )

        console.print(table)

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


@app.command("enable")
def enable_server(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", help="Enable globally for all users"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
) -> None:
    """Enable a server."""
    try:
        if global_scope:
            resolved_user = _resolve_system_user_id(user_id)
            with _get_client(resolved_user) as client:
                response = client.post(f"/v1/servers/{server_id}:enable")
        else:
            resolved_user = _resolve_user_id(user_id)
            with _get_client(resolved_user) as client:
                response = client.post(f"/v1/me/servers/{server_id}:enable")
            response.raise_for_status()

        if global_scope:
            console.print(f"[green]✓[/green] Server '{server_id}' enabled globally.")
        else:
            console.print(f"[green]✓[/green] Server '{server_id}' enabled for user '{resolved_user}'.")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Server '{server_id}' not found.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("disable")
def disable_server(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", help="Disable globally for all users"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
) -> None:
    """Disable a server."""
    try:
        if global_scope:
            resolved_user = _resolve_system_user_id(user_id)
            with _get_client(resolved_user) as client:
                response = client.post(f"/v1/servers/{server_id}:disable")
        else:
            resolved_user = _resolve_user_id(user_id)
            with _get_client(resolved_user) as client:
                response = client.post(f"/v1/me/servers/{server_id}:disable")
            response.raise_for_status()

        if global_scope:
            console.print(f"[green]✓[/green] Server '{server_id}' disabled globally.")
        else:
            console.print(f"[green]✓[/green] Server '{server_id}' disabled for user '{resolved_user}'.")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Server '{server_id}' not found.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("info")
def server_info(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show detailed information about a server."""
    try:
        resolved_user = _resolve_user_id(user_id)
        with _get_client(resolved_user) as client:
            response = client.get(f"/v1/servers/{server_id}")
            response.raise_for_status()
            data = response.json()

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        server = data.get("data", {})
        console.print(f"\n[bold cyan]Server: {server.get('mcp_id')}[/bold cyan]\n")
        console.print(f"[bold]Name:[/bold] {server.get('name')}")
        console.print(f"[bold]Source:[/bold] {server.get('source')}")
        console.print(f"[bold]Transport:[/bold] {server.get('transport')}")
        console.print(f"[bold]Status:[/bold] {server.get('status')}")
        console.print(f"[bold]User Enabled:[/bold] {'Yes' if server.get('user_enabled') else 'No'}")
        console.print(f"[bold]Summary:[/bold] {server.get('summary', 'N/A')}")

        effective_config = server.get("effective_config", {})
        if effective_config:
            console.print("\n[bold]Effective Configuration:[/bold]")
            console.print(f"  Transport: {effective_config.get('transport', 'N/A')}")
            console.print(f"  Tool Call Timeout: {effective_config.get('tool_call_timeout_sec', 'N/A')}s")
            console.print(f"  Idle TTL: {effective_config.get('idle_ttl_sec', 'N/A')}s")
            console.print(f"  Max Concurrency: {effective_config.get('max_concurrency', 'N/A')}")

        diagnostics = server.get("diagnostics", {})
        if diagnostics:
            console.print("\n[bold]Diagnostics:[/bold]")
            console.print(f"  Command allowed: {diagnostics.get('command_allowed', 'N/A')}")
            console.print(f"  Command: {diagnostics.get('command', 'N/A')}")
            deps = diagnostics.get("deps_missing", {})
            if deps:
                console.print(f"  Missing system deps: {deps.get('system', [])}")
                console.print(f"  Missing Python deps: {deps.get('python', [])}")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Server '{server_id}' not found.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("tools")
def list_tools(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    user_id: Annotated[
        str | None,
        typer.Option("--user", help="User ID for request context"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List tools provided by a server."""
    try:
        resolved_user = _resolve_user_id(user_id)
        with _get_client(resolved_user) as client:
            response = client.get(f"/v1/servers/{server_id}/tools")
            response.raise_for_status()
            data = response.json()

        tools = data.get("data", {}).get("tools", [])

        if json_output:
            console.print_json(json.dumps({"tools": tools}, indent=2))
            return

        if not tools:
            console.print(f"[yellow]Server '{server_id}' provides no tools.[/yellow]")
            return

        console.print(f"\n[bold cyan]Tools from {server_id}:[/bold cyan]\n")

        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Description")

        for tool in tools:
            table.add_row(
                tool.get("name", ""),
                tool.get("description", ""),
            )

        console.print(table)

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Server '{server_id}' not found or not running.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None
