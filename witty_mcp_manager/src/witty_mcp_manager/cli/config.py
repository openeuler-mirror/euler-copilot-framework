"""
Config subcommand - manage configuration.

Commands:
- show: Show current configuration
- validate: Validate configuration files
- reload: Reload configuration
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Annotated

import httpx
import typer
from rich.console import Console

from witty_mcp_manager.config.config import load_config

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Manage configuration")


def _get_client() -> httpx.Client:
    """Create HTTP client for UDS communication."""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
    )


@app.command("show")
def show_config(
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show current configuration."""
    try:
        config = load_config()

        if json_output:
            console.print_json(
                json.dumps(
                    {
                        "scan_paths": config.scan_paths,
                        "socket_path": config.socket_path,
                        "idle_session_ttl": config.idle_session_ttl,
                        "command_allowlist": config.command_allowlist,
                    },
                    indent=2,
                )
            )
            return

        console.print("\n[bold cyan]Witty MCP Manager Configuration[/bold cyan]\n")
        console.print(f"[bold]Scan Paths:[/bold] {', '.join(config.scan_paths)}")
        console.print(f"[bold]Socket Path:[/bold] {config.socket_path}")
        console.print(f"[bold]Idle Session TTL:[/bold] {config.idle_session_ttl}s")
        console.print(f"[bold]Command Allowlist:[/bold] {', '.join(config.command_allowlist)}")

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("validate")
def validate_config(
    config_file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Configuration file to validate"),
    ] = None,
) -> None:
    """Validate configuration files."""
    try:
        if config_file:
            # Validate specific file
            if not config_file.exists():
                console.print(f"[red]Error: File not found: {config_file}[/red]")
                raise typer.Exit(code=1)  # noqa: TRY301

            # Try to parse as JSON
            with config_file.open() as f:
                json.load(f)
            console.print(f"[green]✓[/green] {config_file} is valid JSON.")
        else:
            # Validate global config
            load_config()
            console.print("[green]✓[/green] Global configuration is valid.")

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("reload")
def reload_config() -> None:
    """Reload daemon configuration (requires daemon restart)."""
    try:
        with _get_client() as client:
            response = client.post("/v1/config/reload")
            response.raise_for_status()

        console.print("[green]✓[/green] Configuration reloaded.")

    except httpx.ConnectError:
        console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
        console.print("[yellow]Try: systemctl restart witty-mcp-manager[/yellow]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None
