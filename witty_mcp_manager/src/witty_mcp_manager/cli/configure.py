"""
Configure subcommand - configure MCP server credentials and settings.

Supports both TUI interactive mode and pure CLI mode.

Commands/Modes:
- TUI mode (default): Interactive selection and configuration
- CLI mode: Direct configuration via command-line arguments
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - Required at runtime for Typer
from typing import Annotated

import httpx
import typer
import yaml
from rich.console import Console

from witty_mcp_manager.config.config import load_config
from witty_mcp_manager.ipc.auth import HEADER_USER_ID
from witty_mcp_manager.overlay.storage import OverlayStorage
from witty_mcp_manager.registry.models import Override
from witty_mcp_manager.security.redaction import get_redactor

from .permissions import (
    PermissionError as CliPermissionError,
)
from .permissions import (
    get_current_identity,
    resolve_scope,
)

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Configure MCP server credentials")


def _handle_permission_error(err: CliPermissionError) -> None:
    """Handle permission error with nice output."""
    console.print(f"[red]Error: {err}[/red]")
    if err.suggestion:
        console.print(f"[yellow]{err.suggestion}[/yellow]")
    raise typer.Exit(code=1)


def _get_overlay_storage() -> OverlayStorage:
    """Get overlay storage instance."""
    config = load_config()
    return OverlayStorage(config.state_directory)


def _get_client(user_id: str) -> httpx.Client:
    """Create HTTP client for UDS communication."""
    return httpx.Client(
        transport=httpx.HTTPTransport(uds=UDS_PATH),
        base_url="http://localhost",
        timeout=30.0,
        headers={HEADER_USER_ID: user_id},
    )


def _parse_env_arg(env_arg: str) -> tuple[str, str]:
    """Parse KEY=VALUE format."""
    if "=" not in env_arg:
        msg = f"Invalid format: '{env_arg}'. Expected KEY=VALUE."
        raise ValueError(msg)
    key, value = env_arg.split("=", 1)
    if not key:
        msg = f"Invalid format: '{env_arg}'. Key cannot be empty."
        raise ValueError(msg)
    return key, value


def _parse_env_file(env_file: Path) -> dict[str, str]:
    """Parse .env file format."""
    result: dict[str, str] = {}
    content = env_file.read_text(encoding="utf-8")
    for line_num, raw_line in enumerate(content.splitlines(), 1):
        stripped_line = raw_line.strip()
        # Skip empty lines and comments
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if "=" not in stripped_line:
            msg = f"Invalid format at line {line_num}: '{stripped_line}'. Expected KEY=VALUE."
            raise ValueError(msg)
        key, value = stripped_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Remove optional quotes
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        if not key:
            msg = f"Invalid format at line {line_num}: Key cannot be empty."
            raise ValueError(msg)
        result[key] = value
    return result


def _fetch_server_list(user_id: str) -> list[dict[str, object]]:
    """Fetch server list from daemon."""
    with _get_client(user_id) as client:
        response = client.get("/v1/servers", params={"include_disabled": "false"})
        response.raise_for_status()
        data = response.json().get("data", [])
        return list(data)


def _show_current_config(
    mcp_id: str,
    user_id: str | None,
    *,
    is_global: bool,
) -> None:
    """Show current configuration for a server (redacted)."""
    storage = _get_overlay_storage()
    target_user = None if is_global else user_id
    override = storage.load_override(mcp_id, user_id=target_user)

    scope_name = "global" if is_global else f"user/{user_id}"
    console.print(f"\n[bold cyan]Current configuration for {mcp_id} ({scope_name}):[/bold cyan]\n")

    if not override:
        console.print("  (no configuration)")
        return

    redactor = get_redactor()

    if override.env:
        console.print("[bold]Environment variables:[/bold]")
        redacted_env = redactor.redact_env(override.env)
        for key, value in redacted_env.items():
            console.print(f"  {key}={value}")
    else:
        console.print("[bold]Environment variables:[/bold] (none)")

    if override.headers:
        console.print("[bold]HTTP headers:[/bold]")
        redacted_headers = redactor.redact_env(override.headers)
        for key, value in redacted_headers.items():
            console.print(f"  {key}: {value}")
    else:
        console.print("[bold]HTTP headers:[/bold] (none)")

    if override.disabled:
        console.print("[bold]Status:[/bold] disabled")


def _apply_config_via_ipc(
    mcp_id: str,
    user_id: str,
    *,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> bool:
    """Apply configuration via IPC (converts to secret:// references)."""
    payload: dict[str, object] = {}
    if env:
        payload["env"] = env
    if headers:
        payload["headers"] = headers

    if not payload:
        return True

    try:
        with _get_client(user_id) as client:
            response = client.post(f"/v1/me/servers/{mcp_id}:configure", json=payload)
            response.raise_for_status()
            return True
    except httpx.ConnectError:
        return False


def _apply_config_direct(
    mcp_id: str,
    user_id: str | None,
    *,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    is_global: bool = False,
) -> Path:
    """Apply configuration directly to overlay file."""
    storage = _get_overlay_storage()
    storage.ensure_directories()

    target_user = None if is_global else user_id
    scope_name = "global" if is_global else f"user/{user_id}"

    override = storage.load_override(mcp_id, user_id=target_user)
    if override is None:
        override = Override(scope=scope_name)

    if env is not None:
        if override.env is None:
            override.env = {}
        override.env.update(env)

    if headers is not None:
        if override.headers is None:
            override.headers = {}
        override.headers.update(headers)

    return storage.save_override(mcp_id, override, user_id=target_user)


def _clear_config(
    mcp_id: str,
    user_id: str | None,
    *,
    is_global: bool = False,
) -> bool:
    """Clear env and headers from configuration."""
    storage = _get_overlay_storage()
    target_user = None if is_global else user_id

    override = storage.load_override(mcp_id, user_id=target_user)
    if override is None:
        return False

    override.env = {}
    override.headers = {}
    storage.save_override(mcp_id, override, user_id=target_user)
    return True


def _tui_select_server(user_id: str) -> str | None:
    """TUI: Let user select a server from list."""
    import questionary  # noqa: PLC0415

    servers = _fetch_server_list(user_id)
    if not servers:
        console.print("[yellow]No servers found.[/yellow]")
        return None

    choices = [
        questionary.Choice(
            title=f"{s.get('mcp_id')} - {s.get('name', 'Unknown')}",
            value=str(s.get("mcp_id", "")),
        )
        for s in servers
    ]

    result = questionary.select("Select MCP to configure:", choices=choices).ask()
    return str(result) if result is not None else None


def _tui_set_env(mcp_id: str, user_id: str, *, is_global: bool) -> None:
    """TUI: Set environment variable."""
    import questionary  # noqa: PLC0415

    key = questionary.text("Variable name:").ask()
    if not key:
        return
    value = questionary.password("Variable value (hidden):").ask()
    if value is None:
        return

    if not is_global and _apply_config_via_ipc(mcp_id, user_id, env={key: value}):
        console.print(f"[green]✓ Set {key} (stored as secret)[/green]")
    else:
        _apply_config_direct(mcp_id, user_id, env={key: value}, is_global=is_global)
        console.print(f"[green]✓ Set {key}[/green]")


def _tui_set_header(mcp_id: str, user_id: str, *, is_global: bool) -> None:
    """TUI: Set HTTP header."""
    import questionary  # noqa: PLC0415

    key = questionary.text("Header name:").ask()
    if not key:
        return
    value = questionary.password("Header value (hidden):").ask()
    if value is None:
        return

    if not is_global and _apply_config_via_ipc(mcp_id, user_id, headers={key: value}):
        console.print(f"[green]✓ Set {key} header (stored as secret)[/green]")
    else:
        _apply_config_direct(mcp_id, user_id, headers={key: value}, is_global=is_global)
        console.print(f"[green]✓ Set {key} header[/green]")


def _tui_remove_env(mcp_id: str, user_id: str | None, *, is_global: bool) -> None:
    """TUI: Remove environment variable."""
    import questionary  # noqa: PLC0415

    storage = _get_overlay_storage()
    target_user = None if is_global else user_id
    override = storage.load_override(mcp_id, user_id=target_user)

    if not override or not override.env:
        console.print("[yellow]No environment variables to remove.[/yellow]")
        return

    keys = list(override.env.keys())
    key = questionary.select("Select variable to remove:", choices=keys).ask()
    if key and key in override.env:
        del override.env[key]
        storage.save_override(mcp_id, override, user_id=target_user)
        console.print(f"[green]✓ Removed {key}[/green]")


def _tui_remove_header(mcp_id: str, user_id: str | None, *, is_global: bool) -> None:
    """TUI: Remove HTTP header."""
    import questionary  # noqa: PLC0415

    storage = _get_overlay_storage()
    target_user = None if is_global else user_id
    override = storage.load_override(mcp_id, user_id=target_user)

    if not override or not override.headers:
        console.print("[yellow]No headers to remove.[/yellow]")
        return

    keys = list(override.headers.keys())
    key = questionary.select("Select header to remove:", choices=keys).ask()
    if key and key in override.headers:
        del override.headers[key]
        storage.save_override(mcp_id, override, user_id=target_user)
        console.print(f"[green]✓ Removed {key}[/green]")


def _tui_clear_config(mcp_id: str, user_id: str | None, *, is_global: bool) -> None:
    """TUI: Clear all configuration."""
    import questionary  # noqa: PLC0415

    if questionary.confirm("Clear all configuration?", default=False).ask():
        if _clear_config(mcp_id, user_id, is_global=is_global):
            console.print("[green]✓ Configuration cleared[/green]")
        else:
            console.print("[yellow]No configuration to clear.[/yellow]")


def _run_tui_mode(
    mcp_id: str | None,
    user_id: str,
    *,
    is_global: bool,
) -> None:
    """Run TUI interactive mode."""
    try:
        import questionary  # noqa: PLC0415
    except ImportError:
        console.print("[red]Error: TUI mode requires 'questionary' package.[/red]")
        console.print("[yellow]Install with: pip install questionary[/yellow]")
        console.print("[yellow]Or use CLI mode: witty-mcp configure <mcp_id> --env KEY=VALUE[/yellow]")
        raise typer.Exit(code=1) from None

    # If no mcp_id, let user select
    if mcp_id is None:
        selected = _tui_select_server(user_id)
        if selected is None:
            console.print("Cancelled.")
            raise typer.Exit(code=0)
        mcp_id = selected

    # Main configuration loop
    while True:
        _show_current_config(mcp_id, user_id, is_global=is_global)

        action = questionary.select(
            f"\nConfigure {mcp_id}:",
            choices=[
                questionary.Choice("Set environment variable", value="env"),
                questionary.Choice("Set HTTP header", value="header"),
                questionary.Choice("Remove environment variable", value="rm_env"),
                questionary.Choice("Remove HTTP header", value="rm_header"),
                questionary.Choice("Clear all configuration", value="clear"),
                questionary.Choice("Done", value="done"),
            ],
        ).ask()

        if action is None or action == "done":
            console.print("Done.")
            break

        _handle_tui_action(action, mcp_id, user_id, is_global=is_global)


def _handle_tui_action(action: str, mcp_id: str, user_id: str, *, is_global: bool) -> None:
    """Handle a single TUI action."""
    if action == "env":
        _tui_set_env(mcp_id, user_id, is_global=is_global)
    elif action == "header":
        _tui_set_header(mcp_id, user_id, is_global=is_global)
    elif action == "rm_env":
        _tui_remove_env(mcp_id, user_id, is_global=is_global)
    elif action == "rm_header":
        _tui_remove_header(mcp_id, user_id, is_global=is_global)
    elif action == "clear":
        _tui_clear_config(mcp_id, user_id, is_global=is_global)


def _parse_cli_env_args(
    env_list: list[str] | None,
) -> dict[str, str]:
    """Parse --env CLI arguments."""
    result: dict[str, str] = {}
    if not env_list:
        return result
    for env_arg in env_list:
        try:
            key, value = _parse_env_arg(env_arg)
            result[key] = value
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1) from None
    return result


def _parse_cli_from_file(from_file: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Parse --from-file YAML configuration."""
    if not from_file.exists():
        console.print(f"[red]Error: File not found: {from_file}[/red]")
        raise typer.Exit(code=1)

    try:
        data = yaml.safe_load(from_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing {from_file}: {e}[/red]")
        raise typer.Exit(code=1) from None

    if not isinstance(data, dict):
        console.print("[red]Error: YAML file must contain a mapping.[/red]")
        raise typer.Exit(code=1)

    env_dict: dict[str, str] = {}
    headers_dict: dict[str, str] = {}
    if "env" in data and isinstance(data["env"], dict):
        env_dict.update({str(k): str(v) for k, v in data["env"].items()})
    if "headers" in data and isinstance(data["headers"], dict):
        headers_dict.update({str(k): str(v) for k, v in data["headers"].items()})
    return env_dict, headers_dict


def _parse_cli_env_file(env_file: Path) -> dict[str, str]:
    """Parse --env-file configuration."""
    if not env_file.exists():
        console.print(f"[red]Error: File not found: {env_file}[/red]")
        raise typer.Exit(code=1)
    try:
        return _parse_env_file(env_file)
    except ValueError as e:
        console.print(f"[red]Error parsing {env_file}: {e}[/red]")
        raise typer.Exit(code=1) from None


def _apply_cli_config(
    mcp_id: str,
    resolved_user: str | None,
    env_dict: dict[str, str],
    headers_dict: dict[str, str],
    *,
    is_global: bool,
) -> None:
    """Apply configuration from CLI arguments."""
    if not env_dict and not headers_dict:
        console.print("[yellow]Nothing to configure.[/yellow]")
        return

    # Try IPC first for user-level (converts to secret:// references)
    if not is_global and resolved_user and _apply_config_via_ipc(
        mcp_id,
        resolved_user,
        env=env_dict if env_dict else None,
        headers=headers_dict if headers_dict else None,
    ):
        console.print(f"[green]✓ Configuration applied for {mcp_id} (secrets stored securely)[/green]")
        return

    # Fallback to direct file access
    path = _apply_config_direct(
        mcp_id,
        resolved_user,
        env=env_dict if env_dict else None,
        headers=headers_dict if headers_dict else None,
        is_global=is_global,
    )
    console.print(f"[green]✓ Configuration applied for {mcp_id}[/green]")
    console.print(f"  Overlay: {path}")


@app.callback(invoke_without_command=True)
def configure(  # noqa: C901, PLR0913
    ctx: typer.Context,
    mcp_id: Annotated[
        str | None,
        typer.Argument(help="MCP Server ID (optional in TUI mode)"),
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option("--env", "-e", help="Set environment variable (KEY=VALUE)"),
    ] = None,
    header: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="Set HTTP header (KEY=VALUE)"),
    ] = None,
    env_file: Annotated[
        Path | None,
        typer.Option("--env-file", help="Load environment variables from file"),
    ] = None,
    from_file: Annotated[
        Path | None,
        typer.Option("--from-file", "-f", help="Load configuration from YAML file"),
    ] = None,
    show: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--show", "-s", help="Show current configuration"),
    ] = False,
    clear: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--clear", help="Clear all env and headers"),
    ] = False,
    tui: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--tui", "-t", help="Force TUI interactive mode"),
    ] = False,
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="Configure global overlay (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
) -> None:
    """
    Configure MCP server credentials and settings.

    Supports two modes:

    TUI Mode (interactive):
        witty-mcp configure                    # Select MCP and configure
        witty-mcp configure git_mcp            # Configure specific MCP

    CLI Mode (direct):
        witty-mcp configure git_mcp --env GITHUB_TOKEN=xxx
        witty-mcp configure git_mcp --env-file ~/.env
        witty-mcp configure git_mcp --from-file config.yaml
        witty-mcp configure git_mcp --show
        witty-mcp configure git_mcp --clear

    Regular users: Configures current user's overlay.
    Root/sudo users: Must specify --global or --user <user_id>.

    Examples:
        witty-mcp configure git_mcp --env TOKEN=xxx
        sudo witty-mcp configure git_mcp --global --env SHARED_KEY=xxx
        sudo witty-mcp configure git_mcp --user alice --env TOKEN=xxx

    """
    # If a subcommand is invoked, don't run the main callback
    if ctx.invoked_subcommand is not None:
        return

    # Resolve permissions
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="configure",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    resolved_user = scope.user_id
    is_global = scope.is_global

    # Determine mode
    has_cli_args = any([env, header, env_file, from_file, show, clear])

    # TUI mode: no CLI args or explicit --tui
    if tui or not has_cli_args:
        if is_global and resolved_user is None:
            resolved_user = "__system__"
        _run_tui_mode(mcp_id, resolved_user or "__system__", is_global=is_global)
        return

    # CLI mode: require mcp_id
    if mcp_id is None:
        console.print("[red]Error: MCP ID is required for CLI mode.[/red]")
        console.print("[yellow]Use TUI mode without arguments: witty-mcp configure[/yellow]")
        raise typer.Exit(code=1)

    # Handle --show
    if show:
        _show_current_config(mcp_id, resolved_user, is_global=is_global)
        return

    # Handle --clear
    if clear:
        if _clear_config(mcp_id, resolved_user, is_global=is_global):
            console.print(f"[green]✓ Configuration cleared for {mcp_id}[/green]")
        else:
            console.print(f"[yellow]No configuration to clear for {mcp_id}[/yellow]")
        return

    # Collect env and headers using helper functions
    env_dict = _parse_cli_env_args(env)
    headers_dict = _parse_cli_env_args(header)

    if env_file:
        env_dict.update(_parse_cli_env_file(env_file))

    if from_file:
        file_env, file_headers = _parse_cli_from_file(from_file)
        env_dict.update(file_env)
        headers_dict.update(file_headers)

    # Apply configuration
    _apply_cli_config(mcp_id, resolved_user, env_dict, headers_dict, is_global=is_global)
