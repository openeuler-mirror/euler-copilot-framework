"""
Config subcommand - manage configuration.

Commands:
- show: Show current configuration
- validate: Validate configuration files
- reload: Reload configuration
- apply: Apply overlay configuration
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Annotated

import httpx
import typer
import yaml
from rich.console import Console

from witty_mcp_manager.config.config import load_config
from witty_mcp_manager.ipc.auth import HEADER_USER_ID
from witty_mcp_manager.overlay.storage import OverlayStorage
from witty_mcp_manager.registry.models import Override

from .permissions import (
    PermissionError as CliPermissionError,
)
from .permissions import (
    get_current_identity,
    resolve_scope,
)

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Manage configuration")


def _handle_permission_error(err: CliPermissionError) -> None:
    """Handle permission error with nice output."""
    console.print(f"[red]Error: {err}[/red]")
    if err.suggestion:
        console.print(f"[yellow]{err.suggestion}[/yellow]")
    raise typer.Exit(code=1)


def _get_client(user_id: str | None = None) -> httpx.Client:
    """Create HTTP client for UDS communication."""
    headers: dict[str, str] = {}
    if user_id:
        headers[HEADER_USER_ID] = user_id
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
        headers=headers,
    )


def _get_overlay_storage() -> OverlayStorage:
    """Get overlay storage instance for direct file access."""
    config = load_config()
    return OverlayStorage(config.state_directory)


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
                ),
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

            # Try to parse as YAML
            with config_file.open() as f:
                yaml.safe_load(f)
            console.print(f"{config_file} is valid YAML.")
        else:
            # Validate global config
            load_config()
            console.print("Global configuration is valid.")

    except yaml.YAMLError as e:
        console.print(f"[red]Invalid YAML: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("reload")
def reload_config() -> None:
    """Reload daemon configuration (requires daemon restart)."""
    console.print("[yellow]Not supported:[/yellow] IPC API does not expose config reload. Please restart the daemon.")
    raise typer.Exit(code=2)


@app.command("apply")
def apply_config(
    mcp_id: Annotated[str, typer.Argument(help="MCP Server ID")],
    config_file: Annotated[
        Path,
        typer.Option("--file", "-f", help="Overlay config file (YAML/JSON)"),
    ],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="Apply to global overlay (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """
    Apply overlay configuration to a server.

    Regular users: Applies to current user's overlay (no flags needed).
    Root/sudo users: Must specify --global or --user <user_id>.

    --global (-g): System-level overlay (requires root/sudo)
    --user (-u):   User-level overlay

    If daemon is running, uses IPC to convert secrets to secret:// references;
    otherwise writes directly to overlay file.

    Overlay file can contain: env, headers, disabled.

    Examples:
        witty-mcp config apply git_mcp -f overlay.yaml        # Regular user
        sudo witty-mcp config apply git_mcp -f overlay.yaml --global
        sudo witty-mcp config apply git_mcp -f overlay.yaml --user alice

    """
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="config apply",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        if not config_file.exists():
            console.print(f"[red]Error: File not found: {config_file}[/red]")
            raise typer.Exit(code=1)  # noqa: TRY301

        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            console.print("[red]Error: Overlay file must be a mapping.[/red]")
            raise typer.Exit(code=1)  # noqa: TRY301

        if scope.is_global:
            # System-level: directly modify global overlay (no daemon needed)
            _apply_overlay_direct(mcp_id, payload, user_id=None, json_output=json_output)
        else:
            # User-level: try IPC first, fallback to direct file access
            assert scope.user_id is not None
            try:
                _apply_overlay_via_ipc(mcp_id, payload, scope.user_id, json_output)
            except httpx.ConnectError:
                console.print("[yellow]Daemon not running, writing overlay directly.[/yellow]")
                _apply_overlay_direct(mcp_id, payload, user_id=scope.user_id, json_output=json_output)

    except typer.Exit:
        raise
    except yaml.YAMLError as e:
        console.print(f"[red]Invalid YAML: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(code=1) from None


def _apply_overlay_direct(
    mcp_id: str,
    payload: dict[str, object],
    *,
    user_id: str | None,
    json_output: bool,
) -> None:
    """Apply overlay by directly writing to file."""
    storage = _get_overlay_storage()
    storage.ensure_directories()

    scope_name = "global" if user_id is None else f"user/{user_id}"

    # Load existing or create new
    override = storage.load_override(mcp_id, user_id=user_id)
    if override is None:
        override = Override(scope=scope_name)

    # Apply fields from payload
    if "env" in payload and isinstance(payload["env"], dict):
        override.env = {str(k): str(v) for k, v in payload["env"].items()}
    if "headers" in payload and isinstance(payload["headers"], dict):
        override.headers = {str(k): str(v) for k, v in payload["headers"].items()}
    if "disabled" in payload:
        override.disabled = bool(payload["disabled"])

    path = storage.save_override(mcp_id, override, user_id=user_id)

    if json_output:
        console.print_json(
            json.dumps(
                {
                    "success": True,
                    "mcp_id": mcp_id,
                    "scope": scope_name,
                    "path": str(path),
                },
                indent=2,
            ),
        )
    else:
        console.print(f"Applied overlay for '{mcp_id}' ({scope_name}).")
        console.print(f"  Overlay: {path}")


def _apply_overlay_via_ipc(
    mcp_id: str,
    payload: dict[str, object],
    user_id: str,  # Required, not optional
    json_output: bool,  # noqa: FBT001
) -> None:
    """Apply overlay via IPC (converts secrets to references)."""
    # Only send env/headers via IPC (other fields not supported)
    allowed_keys = {"env", "headers"}
    filtered_payload = {k: v for k, v in payload.items() if k in allowed_keys}

    if not filtered_payload:
        console.print("[yellow]Warning: No valid fields for IPC (only env/headers supported).[/yellow]")
        return

    endpoint = f"/v1/me/servers/{mcp_id}/configure"

    with _get_client(user_id) as client:
        response = client.post(endpoint, json=filtered_payload)
        response.raise_for_status()
        data = response.json()

    if json_output:
        console.print_json(json.dumps(data, indent=2))
    else:
        console.print(f"Applied overlay for '{mcp_id}' (user={user_id}).")
