"""
Logs subcommand - view daemon logs.

Commands:
- tail: Tail daemon logs
- show: Show recent logs
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from .renderer import print_template

console = Console()
app = typer.Typer(add_completion=False, help="View logs")


@app.command("tail")
def tail_logs(
    follow: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--follow", "-f", help="Follow log output"),
    ] = False,
    lines: Annotated[
        int,
        typer.Option("--lines", "-n", help="Number of lines to show"),
    ] = 50,
) -> None:
    """Tail daemon logs using journalctl."""
    import subprocess  # noqa: PLC0415

    cmd = ["journalctl", "-u", "witty-mcp-manager", "-n", str(lines)]
    if follow:
        cmd.append("-f")

    try:
        subprocess.run(cmd, check=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        print_template(console, "error_journalctl.txt", {"error": str(e)})
        raise typer.Exit(code=1) from None
    except FileNotFoundError:
        print_template(console, "error_journalctl_not_found.txt", {})
        raise typer.Exit(code=1) from None


@app.command("show")
def show_logs(
    lines: Annotated[
        int,
        typer.Option("--lines", "-n", help="Number of lines to show"),
    ] = 100,
    priority: Annotated[
        str | None,
        typer.Option("--priority", "-p", help="Filter by priority (e.g., err, warning, info)"),
    ] = None,
) -> None:
    """Show recent daemon logs."""
    import subprocess  # noqa: PLC0415

    cmd = ["journalctl", "-u", "witty-mcp-manager", "-n", str(lines), "--no-pager"]
    if priority:
        cmd.extend(["-p", priority])

    try:
        subprocess.run(cmd, check=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        print_template(console, "error_journalctl.txt", {"error": str(e)})
        raise typer.Exit(code=1) from None
    except FileNotFoundError:
        print_template(console, "error_journalctl_not_found.txt", {})
        raise typer.Exit(code=1) from None
