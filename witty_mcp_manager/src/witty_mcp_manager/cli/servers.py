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

import json
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Manage MCP servers")


def _get_client() -> httpx.Client:
    """Create HTTP client for UDS communication."""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
    )


@app.command("list")
def list_servers(
    enabled_only: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--enabled", help="Show only enabled servers"),
    ] = False,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List all discovered MCP servers."""
    try:
        with _get_client() as client:
            response = client.get("/v1/servers")
            response.raise_for_status()
            data = response.json()

        servers = data.get("servers", [])
        if enabled_only:
            servers = [s for s in servers if s.get("enabled", False)]

        if json_output:
            console.print_json(json.dumps({"servers": servers}, indent=2))
            return

        if not servers:
            console.print("[yellow]No servers found.[/yellow]")
            return

        table = Table(title="MCP Servers")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Transport", style="blue")
        table.add_column("Enabled", style="green")
        table.add_column("Description")

        for server in servers:
            table.add_row(
                server.get("canonical_id", ""),
                server.get("source_type", ""),
                server.get("transport_type", ""),
                "✓" if server.get("enabled", False) else "✗",
                server.get("description", ""),
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
) -> None:
    """Enable a server."""
    try:
        with _get_client() as client:
            response = client.post(
                f"/v1/servers/{server_id}/enable",
                json={"scope": "global" if global_scope else "user"},
            )
            response.raise_for_status()

        scope_str = "globally" if global_scope else "for current user"
        console.print(f"[green]✓[/green] Server '{server_id}' enabled {scope_str}.")

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
) -> None:
    """Disable a server."""
    try:
        with _get_client() as client:
            response = client.post(
                f"/v1/servers/{server_id}/disable",
                json={"scope": "global" if global_scope else "user"},
            )
            response.raise_for_status()

        scope_str = "globally" if global_scope else "for current user"
        console.print(f"[green]✓[/green] Server '{server_id}' disabled {scope_str}.")

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
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show detailed information about a server."""
    try:
        with _get_client() as client:
            response = client.get(f"/v1/servers/{server_id}")
            response.raise_for_status()
            data = response.json()

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        server = data.get("server", {})
        console.print(f"\n[bold cyan]Server: {server.get('canonical_id')}[/bold cyan]\n")
        console.print(f"[bold]Type:[/bold] {server.get('source_type')}")
        console.print(f"[bold]Transport:[/bold] {server.get('transport_type')}")
        console.print(f"[bold]Enabled:[/bold] {'Yes' if server.get('enabled') else 'No'}")
        console.print(f"[bold]Description:[/bold] {server.get('description', 'N/A')}")

        config = server.get("config", {})
        if config:
            console.print("\n[bold]Configuration:[/bold]")
            console.print(f"  Command: {config.get('command', 'N/A')}")
            console.print(f"  Args: {config.get('args', [])}")
            console.print(f"  Env: {config.get('env', {})}")
            console.print(f"  Timeout: {config.get('timeout', 'default')}")

        diagnostics = server.get("diagnostics", {})
        if diagnostics:
            console.print("\n[bold]Diagnostics:[/bold]")
            console.print(f"  Command allowed: {diagnostics.get('command_allowed', 'N/A')}")
            console.print(f"  Missing dependencies: {diagnostics.get('missing_dependencies', [])}")

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
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List tools provided by a server."""
    try:
        with _get_client() as client:
            response = client.get(f"/v1/servers/{server_id}/tools")
            response.raise_for_status()
            data = response.json()

        tools = data.get("tools", [])

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
