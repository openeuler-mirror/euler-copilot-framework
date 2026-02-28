"""
Servers subcommand - manage MCP servers.

This CLI supports both privileged (root/sudo) and regular user operations.
- Privileged users: Must specify --global or --user <user_id>
- Regular users: Automatically use current username

Commands:
- list: List all discovered servers
- enable: Enable a server
- disable: Disable a server
- info: Show detailed information about a server
- tools: List tools provided by a server
- inspect: Show raw configuration and overlay details
- overlay: Show/manage overlay configuration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import httpx
import typer
import yaml
from rich.console import Console
from rich.table import Table

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
    resolve_user_for_ipc,
)

UDS_PATH = "/run/witty/mcp-manager.sock"

console = Console()
app = typer.Typer(add_completion=False, help="Manage MCP servers")


def _get_overlay_storage() -> OverlayStorage:
    """Get overlay storage instance for direct file access."""
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


def _handle_permission_error(err: CliPermissionError) -> None:
    """Handle permission error with nice output."""
    console.print(f"[red]Error: {err}[/red]")
    if err.suggestion:
        console.print(f"[yellow]{err.suggestion}[/yellow]")
    raise typer.Exit(code=1)


def _enabled_label(*, system_enabled: bool) -> str:
    return "enabled" if system_enabled else "disabled"


_SENSITIVE_ARG_KEYS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
)


def _load_server_entry(
    install_root: str | None,
    upstream_key: str | None,
    mcp_id: str,
) -> dict[str, object]:
    entry: dict[str, object] = {}
    if not install_root:
        return entry
    config_path = Path(install_root) / "mcp_config.json"
    if not config_path.exists():
        return entry
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        if upstream_key and upstream_key in servers and isinstance(servers[upstream_key], dict):
            entry = servers[upstream_key]
        elif mcp_id in servers and isinstance(servers[mcp_id], dict):
            entry = servers[mcp_id]
        elif len(servers) == 1:
            only_key = next(iter(servers.keys()))
            entry = servers[only_key] if isinstance(servers[only_key], dict) else {}
    except Exception:  # noqa: BLE001
        entry = {}
    return entry


def _infer_transport(entry: dict[str, object]) -> str:
    transport_value = entry.get("transport")
    transport = transport_value if isinstance(transport_value, str) else ""
    if transport:
        return transport
    if isinstance(entry.get("sse"), dict) or isinstance(entry.get("url"), str):
        return "sse"
    if isinstance(entry.get("stdio"), dict) or isinstance(entry.get("command"), str):
        return "stdio"
    return ""


def _as_dict(value: object | None) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object | None) -> str | None:
    return value if isinstance(value, str) else None


def _as_str_dict(value: object | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _extract_stdio(entry: dict[str, object]) -> tuple[str | None, list[object] | None, dict[str, object] | None]:
    stdio = _as_dict(entry.get("stdio"))
    command = _as_str(entry.get("command"))
    if command is None:
        command = _as_str(stdio.get("command"))
    args_value = entry.get("args")
    args = args_value if isinstance(args_value, list) else None
    if args is None:
        stdio_args = stdio.get("args")
        args = stdio_args if isinstance(stdio_args, list) else None
    env_value = entry.get("env")
    env = env_value if isinstance(env_value, dict) else None
    if env is None:
        stdio_env = stdio.get("env")
        env = stdio_env if isinstance(stdio_env, dict) else None
    return command, args, env


def _redact_args(args: list[object] | None) -> list[str]:
    if not args:
        return []
    redactor = get_redactor()
    redacted: list[str] = []
    skip_next = False
    for idx, raw in enumerate(args):
        if skip_next:
            skip_next = False
            redacted.append(redactor.MASK_SHORT)
            continue
        arg = str(raw)
        lowered = arg.lower()
        if any(key in lowered for key in _SENSITIVE_ARG_KEYS):
            if "=" in arg:
                key, _value = arg.split("=", 1)
                redacted.append(f"{key}={redactor.MASK_SHORT}")
                continue
            if idx + 1 < len(args):
                redacted.append(arg)
                skip_next = True
                continue
        redacted.append(redactor.redact_value(arg))
    return redacted


def _fetch_enabled_ids(resolved_user: str) -> set[str]:
    with _get_client(resolved_user) as client:
        enabled_resp = client.get("/v1/servers", params={"include_disabled": "false"})
        enabled_resp.raise_for_status()
        enabled_servers = enabled_resp.json().get("data", [])
    return {s.get("mcp_id", "") for s in enabled_servers}


def _fetch_server_detail(resolved_user: str, mcp_id: str) -> dict[str, object]:
    with _get_client(resolved_user) as client:
        detail_resp = client.get(f"/v1/servers/{mcp_id}")
        detail_resp.raise_for_status()
        result = detail_resp.json().get("data", {})
        if isinstance(result, dict):
            return result
        return {}


def _format_command_line(entry: dict[str, object]) -> str | None:
    command, args, _env = _extract_stdio(entry)
    if not command:
        return None
    if args:
        return " ".join([command, *_redact_args(args)])
    return command


def _render_server_header(server: dict[str, object], resolved_user: str) -> None:
    console.print(f"\n[bold cyan]Server ID: {server.get('mcp_id')}[/bold cyan]\n")
    console.print(f"[bold]Display Name:[/bold] {server.get('name')}")
    console.print(f"[bold]Summary:[/bold] {server.get('summary', 'N/A')}")
    console.print(f"[bold]Transport:[/bold] {server.get('transport')}")
    source_label = server.get("source")
    rpm_name = _load_rpm_name(cast("str | None", server.get("install_root")))
    if source_label == "rpm" and rpm_name:
        source_label = f"rpm ({rpm_name})"
    console.print(f"[bold]Source:[/bold] {source_label}")
    console.print(f"[bold]Install Root:[/bold] {server.get('install_root', 'N/A')}")
    console.print(f"[bold]Upstream Key:[/bold] {server.get('upstream_key', 'N/A')}")

    system_enabled = True
    try:
        enabled_ids = _fetch_enabled_ids(resolved_user)
        system_enabled = server.get("mcp_id") in enabled_ids
    except Exception:  # noqa: BLE001
        system_enabled = True
    console.print(f"[bold]Status:[/bold] {_enabled_label(system_enabled=system_enabled)}")
    console.print(f"[bold]Health:[/bold] {server.get('status')}")
    if server.get("status_reason"):
        console.print(f"[bold]Health Reason:[/bold] {server.get('status_reason')}")


def _render_effective_config(server: dict[str, object]) -> None:
    effective_config = server.get("effective_config", {})
    entry = _load_server_entry(
        cast("str | None", server.get("install_root")),
        cast("str | None", server.get("upstream_key")),
        str(server.get("mcp_id", "")),
    )
    command_line = _format_command_line(entry)
    if command_line:
        console.print(f"[bold]Command:[/bold] {command_line}")
    effective_config = _as_dict(effective_config)
    if effective_config:
        console.print("\n[bold]Effective Config:[/bold]")
        console.print(f"  Tool Call Timeout: {effective_config.get('tool_call_timeout_sec', 'N/A')}s")
        console.print(f"  Idle TTL: {effective_config.get('idle_ttl_sec', 'N/A')}s")
        console.print(f"  Concurrency: {effective_config.get('max_concurrency', 'N/A')} per user")
        env = _as_str_dict(effective_config.get("env"))
        if env:
            redacted_env = get_redactor().redact_env(env)
            console.print(f"  Environment: {redacted_env}")
        else:
            console.print("  Environment: (none)")


def _print_command_status(command_allowed: object, command: object) -> None:
    """Print command allowlist status."""
    if command_allowed is True:
        console.print(f"  [green][OK][/green]   Command '{command}' is allowed")
    elif command_allowed is False:
        console.print(f"  [red][FAIL][/red] Command '{command}' is not allowed")


def _print_files_status(files_valid: object) -> None:
    """Print files validity status."""
    if files_valid is True:
        console.print("  [green][OK][/green]   All required files present")
    elif files_valid is False:
        console.print("  [red][FAIL][/red] Required files missing")


def _print_deps_status(deps: object) -> None:
    """Print dependency status."""
    if not isinstance(deps, dict):
        return
    system_deps = deps.get("system", [])
    python_deps = deps.get("python", [])
    if system_deps:
        console.print(f"  [yellow][WARN][/yellow] Missing system dependency: {', '.join(system_deps)}")
        console.print(f"          Suggestion: dnf install {' '.join(system_deps)}")
    if python_deps:
        console.print(f"  [yellow][WARN][/yellow] Missing Python dependency: {', '.join(python_deps)}")
        console.print("          Suggestion: pip install <package>")
    if not system_deps and not python_deps:
        console.print("  [green][OK][/green]   No missing dependencies")


def _print_diagnostics(diagnostics: dict[str, object]) -> None:
    """Print server diagnostics."""
    console.print("\n[bold]Diagnostics:[/bold]")
    _print_command_status(diagnostics.get("command_allowed"), diagnostics.get("command", ""))
    _print_files_status(diagnostics.get("files_valid"))
    _print_deps_status(diagnostics.get("deps_missing", {}))
    errors = diagnostics.get("errors", [])
    if isinstance(errors, list):
        for err in errors:
            console.print(f"  [red][FAIL][/red] {err}")


def _load_rpm_name(install_root: str | None) -> str | None:
    if not install_root:
        return None
    rpm_path = Path(install_root) / "mcp-rpm.yaml"
    if not rpm_path.exists():
        return None
    try:
        with rpm_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            name = data.get("name")
            return str(name) if name else None
    except Exception:  # noqa: BLE001
        return None
    return None


def _get_server_transport(resolved_user: str, mcp_id: str) -> str:
    """Get transport type for a server."""
    try:
        detail = _fetch_server_detail(resolved_user, mcp_id)
        entry = _load_server_entry(
            cast("str | None", detail.get("install_root")),
            cast("str | None", detail.get("upstream_key")),
            mcp_id,
        )
        detail_transport = detail.get("transport")
        return _infer_transport(entry) or (detail_transport if isinstance(detail_transport, str) else "")
    except Exception:  # noqa: BLE001
        return ""


def _render_servers_table(
    servers: list[dict[str, object]],
    resolved_user: str,
    *,
    include_disabled: bool,
) -> tuple[Table, int]:
    """Render servers as a Rich table, return table and enabled count."""
    table = Table(title="MCP Servers")
    table.add_column("MCP_ID", style="cyan")
    table.add_column("DISPLAY_NAME", style="magenta")
    table.add_column("SOURCE", style="blue")
    table.add_column("TRANSPORT", style="blue")
    table.add_column("STATUS", style="green")

    enabled_ids = _fetch_enabled_ids(resolved_user) if include_disabled else set()
    enabled_count = 0

    for server in servers:
        mcp_id = server.get("mcp_id", "")
        system_enabled = True if not include_disabled else mcp_id in enabled_ids
        if system_enabled:
            enabled_count += 1
        transport = _get_server_transport(resolved_user, str(mcp_id))
        table.add_row(
            str(mcp_id),
            str(server.get("name", "")),
            str(server.get("source", "")),
            transport,
            _enabled_label(system_enabled=system_enabled),
        )

    return table, enabled_count


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
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="List with global context (root/sudo only)"),
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
    List all discovered MCP servers.

    Requires daemon to be running.

    Regular users: Automatically uses current username.
    Root/sudo users: Must specify --user <user_id> or --global.
    """
    try:
        identity = get_current_identity()
        # For list, we need a user context for IPC
        # --global doesn't make sense for listing (we always list all servers)
        # but we accept it for consistency
        if global_scope:
            # Use a system context user_id
            resolved_user = user_id if user_id else "__system__"
        else:
            resolved_user = resolve_user_for_ipc(identity, user_flag=user_id, operation="servers list")
    except CliPermissionError as e:
        _handle_permission_error(e)
        return  # unreachable, but satisfies type checker

    try:
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

        table, enabled_count = _render_servers_table(
            servers,
            resolved_user,
            include_disabled=include_disabled,
        )
        console.print(table)

        total = len(servers)
        disabled_count = total - enabled_count
        console.print(f"\nTotal: {total} servers ({enabled_count} enabled, {disabled_count} disabled)")

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
        typer.Option("--global", "-g", help="System-level enable (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
) -> None:
    """
    Enable a server.

    Regular users: Automatically enables for current user.
    Root/sudo users: Must specify --global or --user <user_id>.

    --global (-g): System-level enable, affects all users.
    --user (-u):   User-level enable for specified user.

    Examples:
        witty-mcp servers enable git_mcp              # Regular user
        sudo witty-mcp servers enable git_mcp --global
        sudo witty-mcp servers enable git_mcp --user alice

    """
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="servers enable",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        storage = _get_overlay_storage()
        storage.ensure_directories()

        if scope.is_global:
            # System-level: directly modify global overlay
            override = storage.load_override(server_id, user_id=None)
            if override:
                override.disabled = False
            else:
                override = Override(scope="global", disabled=False)
            path = storage.save_override(server_id, override, user_id=None)
            console.print(f"Server '{server_id}' enabled globally (system-level).")
            console.print(f"  Overlay: {path}")
        else:
            # User-level: directly modify user overlay
            override = storage.load_override(server_id, user_id=scope.user_id)
            if override:
                override.disabled = False
            else:
                override = Override(scope=f"user/{scope.user_id}", disabled=False)
            path = storage.save_override(server_id, override, user_id=scope.user_id)
            console.print(f"Server '{server_id}' enabled for user '{scope.user_id}'.")
            console.print(f"  Overlay: {path}")

    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("disable")
def disable_server(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="System-level disable (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
) -> None:
    """
    Disable a server.

    Regular users: Automatically disables for current user.
    Root/sudo users: Must specify --global or --user <user_id>.

    --global (-g): System-level disable, affects all users.
    --user (-u):   User-level disable for specified user.

    Examples:
        witty-mcp servers disable git_mcp              # Regular user
        sudo witty-mcp servers disable git_mcp --global
        sudo witty-mcp servers disable git_mcp --user alice

    """
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="servers disable",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        storage = _get_overlay_storage()
        storage.ensure_directories()

        if scope.is_global:
            # System-level: directly modify global overlay
            override = storage.load_override(server_id, user_id=None)
            if override:
                override.disabled = True
            else:
                override = Override(scope="global", disabled=True)
            path = storage.save_override(server_id, override, user_id=None)
            console.print(f"Server '{server_id}' disabled globally (system-level).")
            console.print(f"  Overlay: {path}")
        else:
            # User-level: directly modify user overlay
            override = storage.load_override(server_id, user_id=scope.user_id)
            if override:
                override.disabled = True
            else:
                override = Override(scope=f"user/{scope.user_id}", disabled=True)
            path = storage.save_override(server_id, override, user_id=scope.user_id)
            console.print(f"Server '{server_id}' disabled for user '{scope.user_id}'.")
            console.print(f"  Overlay: {path}")

    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("info")
def server_info(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
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
    Show detailed information about a server.

    Requires daemon to be running.

    Regular users: Automatically uses current username.
    Root/sudo users: Must specify --user <user_id>.
    """
    try:
        identity = get_current_identity()
        resolved_user = resolve_user_for_ipc(identity, user_flag=user_id, operation="servers info")
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        with _get_client(resolved_user) as client:
            response = client.get(f"/v1/servers/{server_id}")
            response.raise_for_status()
            data = response.json()

        if json_output:
            console.print_json(json.dumps(data, indent=2))
            return

        server = data.get("data", {})
        _render_server_header(server, resolved_user)
        _render_effective_config(server)

        diagnostics = server.get("diagnostics", {})
        if diagnostics:
            _print_diagnostics(diagnostics)

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
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """
    List tools provided by a server.

    Requires daemon to be running.

    Regular users: Automatically uses current username.
    Root/sudo users: Must specify --user <user_id>.
    """
    try:
        identity = get_current_identity()
        resolved_user = resolve_user_for_ipc(identity, user_flag=user_id, operation="servers tools")
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
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


def _print_overlay_section(server_id: str, user_id: str | None) -> None:
    """Print overlay section for inspect command."""
    storage = _get_overlay_storage()
    console.print("\n[bold]Global Overlay:[/bold]")
    global_override = storage.load_override(server_id, user_id=None)
    if global_override:
        console.print_json(json.dumps(global_override.model_dump(exclude_none=True), indent=2))
    else:
        console.print("  (none)")

    if user_id:
        console.print(f"\n[bold]User Overlay ({user_id}):[/bold]")
        user_override = storage.load_override(server_id, user_id=user_id)
        if user_override:
            console.print_json(json.dumps(user_override.model_dump(exclude_none=True), indent=2))
        else:
            console.print("  (none)")


def _print_server_detail_section(
    server: dict[str, object],
    server_id: str,
    user_id: str | None,
) -> None:
    """Print server detail section for inspect command."""
    console.print("[bold]Server Detail (from daemon):[/bold]")
    _render_server_header(server, user_id or "unknown")
    _render_effective_config(server)
    diagnostics = _as_dict(server.get("diagnostics"))
    if diagnostics:
        _print_diagnostics(diagnostics)

    console.print("\n[bold]Raw mcp_config.json entry:[/bold]")
    install_root = cast("str | None", server.get("install_root"))
    upstream_key = cast("str | None", server.get("upstream_key"))
    entry = _load_server_entry(install_root, upstream_key, server_id)
    if entry:
        console.print_json(json.dumps(entry, indent=2, default=str))
    else:
        console.print("  (not found or empty)")


@app.command("inspect")
def inspect_server(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="Use global context (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
    show_overlay: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--overlay", "-o", help="Show overlay configuration details"),
    ] = False,
    json_output: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """
    Inspect raw configuration and diagnostics for a server.

    --overlay shows both global and user overlay configurations.
    Works without daemon when using --overlay only.

    Regular users: Automatically uses current username.
    Root/sudo users: Must specify --user <user_id> or --global.
    """
    resolved_user: str | None = None

    # Determine user context
    if show_overlay and not global_scope and not user_id:
        # --overlay only mode: can work without user context for global overlay
        resolved_user = None
    else:
        try:
            identity = get_current_identity()
            if global_scope:
                resolved_user = "__system__"
            else:
                resolved_user = resolve_user_for_ipc(identity, user_flag=user_id, operation="servers inspect")
        except CliPermissionError as e:
            if show_overlay:
                # Fallback: show global overlay only
                resolved_user = None
            else:
                _handle_permission_error(e)
                return

    server, daemon_available = _try_fetch_server_detail(
        resolved_user,
        server_id,
        require_daemon=not show_overlay,
    )

    output = _build_inspect_output(
        server_id,
        server,
        resolved_user,
        daemon_available=daemon_available,
        show_overlay=show_overlay,
    )

    if json_output:
        console.print_json(json.dumps(output, indent=2, default=str))
        return

    console.print(f"\n[bold cyan]Inspect: {server_id}[/bold cyan]\n")

    if daemon_available and server:
        _print_server_detail_section(server, server_id, resolved_user)
    elif not daemon_available:
        console.print("[yellow]Daemon not running - showing overlay info only.[/yellow]")

    if show_overlay:
        _print_overlay_section(server_id, resolved_user)


def _try_fetch_server_detail(
    user_id: str | None,
    server_id: str,
    *,
    require_daemon: bool,
) -> tuple[dict[str, object], bool]:
    """Try to fetch server detail, handling connection errors."""
    if user_id is None:
        if require_daemon:
            console.print("[red]Error: --user <user_id> is required for daemon operations.[/red]")
            raise typer.Exit(code=1)
        return {}, False
    try:
        return _fetch_server_detail(user_id, server_id), True
    except httpx.ConnectError:
        if require_daemon:
            console.print("[red]Error: Cannot connect to witty-mcp-manager daemon.[/red]")
            console.print("[yellow]Use --overlay to view overlay config without daemon.[/yellow]")
            raise typer.Exit(code=1) from None
        return {}, False
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            console.print(f"[red]Error: Server '{server_id}' not found.[/red]")
        else:
            console.print(f"[red]HTTP error {e.response.status_code}: {e.response.text}[/red]")
        raise typer.Exit(code=1) from None


def _build_inspect_output(
    server_id: str,
    server: dict[str, object],
    user_id: str | None,
    *,
    daemon_available: bool,
    show_overlay: bool,
) -> dict[str, object]:
    """Build inspect output dictionary."""
    output: dict[str, object] = {"server_id": server_id}

    if daemon_available and server:
        install_root = cast("str | None", server.get("install_root"))
        upstream_key = cast("str | None", server.get("upstream_key"))
        entry = _load_server_entry(install_root, upstream_key, server_id)
        output["mcp_config_entry"] = entry
        output["server_detail"] = server

    if show_overlay:
        storage = _get_overlay_storage()
        global_override = storage.load_override(server_id, user_id=None)
        overlays: dict[str, object] = {
            "global": global_override.model_dump(exclude_none=True) if global_override else None,
        }
        if user_id:
            user_override = storage.load_override(server_id, user_id=user_id)
            overlays[f"user/{user_id}"] = user_override.model_dump(exclude_none=True) if user_override else None
        output["overlays"] = overlays

    return output


def _print_single_overlay(label: str, override: Override | None) -> None:
    """Print a single overlay."""
    console.print(f"\n[bold]{label}:[/bold]")
    if override:
        console.print_json(json.dumps(override.model_dump(exclude_none=True), indent=2))
    else:
        console.print("  (none)")


@app.command("overlay")
def show_overlay(  # noqa: C901
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="Show global overlay (root/sudo only)"),
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
    Show overlay configuration for a server.

    This command works without the daemon running.

    Regular users: Shows current user's overlay (no flags needed).
    Root/sudo users: Must specify --global or --user <user_id>.

    Examples:
        witty-mcp servers overlay git_mcp                  # Regular user
        sudo witty-mcp servers overlay git_mcp --global
        sudo witty-mcp servers overlay git_mcp --user alice

    """
    try:
        identity = get_current_identity()

        # For regular users, auto-resolve to current user
        if not identity.is_privileged and not global_scope and not user_id:
            user_id = identity.real_username
        elif identity.is_privileged and not global_scope and not user_id:
            console.print("[red]Error: Must specify --global or --user <user_id> when running as root/sudo.[/red]")
            raise typer.Exit(code=1)  # noqa: TRY301

        # Check permission for --global
        if global_scope and not identity.is_privileged:
            console.print("[red]Error: --global requires root/sudo privileges.[/red]")
            raise typer.Exit(code=1)  # noqa: TRY301

        storage = _get_overlay_storage()
        result: dict[str, object] = {"server_id": server_id}

        if global_scope:
            global_override = storage.load_override(server_id, user_id=None)
            result["global"] = global_override.model_dump(exclude_none=True) if global_override else None

        if user_id:
            user_override = storage.load_override(server_id, user_id=user_id)
            result[f"user/{user_id}"] = user_override.model_dump(exclude_none=True) if user_override else None

        if json_output:
            console.print_json(json.dumps(result, indent=2))
            return

        console.print(f"\n[bold cyan]Overlay for: {server_id}[/bold cyan]")
        if global_scope:
            global_override = storage.load_override(server_id, user_id=None)
            _print_single_overlay("Global Overlay", global_override)
        if user_id:
            user_override = storage.load_override(server_id, user_id=user_id)
            _print_single_overlay(f"User Overlay ({user_id})", user_override)

    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None


@app.command("overlay-reset")
def reset_overlay(
    server_id: Annotated[str, typer.Argument(help="Server canonical ID")],
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="Reset global overlay (root/sudo only)"),
    ] = False,
    user_id: Annotated[
        str | None,
        typer.Option("--user", "-u", help="User ID (root/sudo can specify any user)"),
    ] = None,
    force: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """
    Reset (delete) overlay configuration for a server.

    This removes the overlay file, reverting the server to default configuration.
    Works without the daemon running.

    Regular users: Resets current user's overlay (no flags needed).
    Root/sudo users: Must specify --global or --user <user_id>.

    Examples:
        witty-mcp servers overlay-reset git_mcp              # Regular user
        sudo witty-mcp servers overlay-reset git_mcp --global
        sudo witty-mcp servers overlay-reset git_mcp --user alice

    """
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="servers overlay-reset",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        storage = _get_overlay_storage()
        target_user = None if scope.is_global else scope.user_id

        override = storage.load_override(server_id, user_id=target_user)
        if not override:
            console.print(f"[yellow]No {scope.scope_name} overlay found for '{server_id}'.[/yellow]")
            return

        if not force:
            console.print(f"[bold]Current {scope.scope_name} overlay for '{server_id}':[/bold]")
            console.print_json(json.dumps(override.model_dump(exclude_none=True), indent=2))
            if not typer.confirm("Delete this overlay?"):
                console.print("Cancelled.")
                return

        storage.delete_override(server_id, user_id=target_user)
        console.print(f"Deleted {scope.scope_name} overlay for '{server_id}'.")

    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None


def _list_overlays_json(
    storage: OverlayStorage,
    scope_name: str,
    server_ids: list[str],
    target_user: str | None,
) -> None:
    """Output overlay list as JSON."""
    overlays = []
    for server_id in server_ids:
        override = storage.load_override(server_id, user_id=target_user)
        if override:
            overlays.append({"server_id": server_id, "overlay": override.model_dump(exclude_none=True)})
    console.print_json(json.dumps({"scope": scope_name, "overlays": overlays}, indent=2))


def _list_overlays_table(
    storage: OverlayStorage,
    scope_name: str,
    server_ids: list[str],
    target_user: str | None,
) -> None:
    """Output overlay list as table."""
    console.print(f"\n[bold]{scope_name.title()} Overlays:[/bold]\n")
    if not server_ids:
        console.print("  (none)")
        return

    table = Table()
    table.add_column("Server ID", style="cyan")
    table.add_column("Disabled", style="yellow")
    table.add_column("Has Env", style="blue")
    table.add_column("Has Headers", style="blue")

    for server_id in sorted(server_ids):
        override = storage.load_override(server_id, user_id=target_user)
        if override:
            table.add_row(
                server_id,
                "yes" if override.disabled else "no",
                "yes" if override.env else "no",
                "yes" if override.headers else "no",
            )

    console.print(table)
    console.print(f"\nTotal: {len(server_ids)} overlays")


@app.command("overlay-list")
def list_overlays(
    global_scope: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--global", "-g", help="List global overlays (root/sudo only)"),
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
    List all overlay files.

    Works without the daemon running.

    Regular users: Lists current user's overlays (no flags needed).
    Root/sudo users: Must specify --global or --user <user_id>.

    Examples:
        witty-mcp servers overlay-list                   # Regular user
        sudo witty-mcp servers overlay-list --global
        sudo witty-mcp servers overlay-list --user alice

    """
    try:
        identity = get_current_identity()
        scope = resolve_scope(
            identity,
            global_flag=global_scope,
            user_flag=user_id,
            operation="servers overlay-list",
        )
    except CliPermissionError as e:
        _handle_permission_error(e)
        return

    try:
        storage = _get_overlay_storage()
        target_user = None if scope.is_global else scope.user_id
        overlay_dir = storage.global_dir if scope.is_global else storage.users_dir / (scope.user_id or "")

        if not overlay_dir.exists():
            if json_output:
                console.print_json(json.dumps({"scope": scope.scope_name, "overlays": []}, indent=2))
            else:
                console.print(f"[yellow]No {scope.scope_name} overlays found.[/yellow]")
            return

        server_ids = [f.stem for f in overlay_dir.glob("*.json")]

        if json_output:
            _list_overlays_json(storage, scope.scope_name, server_ids, target_user)
        else:
            _list_overlays_table(storage, scope.scope_name, server_ids, target_user)

    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None
