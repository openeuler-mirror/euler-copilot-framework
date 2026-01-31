"""`witty-mcp` command line interface.

This is currently a lightweight skeleton to provide a stable entrypoint for
packaging and integration. Subcommands will be implemented incrementally.
"""

from __future__ import annotations

import typer
from rich.console import Console

from witty_mcp_manager import __version__

console = Console()
app = typer.Typer(add_completion=False, help="Witty MCP Manager CLI")


@app.command()
def version() -> None:
    """Print the version."""

    console.print(__version__)


@app.command()
def daemon(debug: bool = typer.Option(False, "--debug", help="Enable debug output")) -> None:
    """Run the daemon process.

    Note: daemon implementation is not yet available in this repository state.
    """

    if debug:
        console.print("[yellow]daemon --debug requested (daemon not implemented yet).[/yellow]")
    console.print("[red]daemon mode is not implemented yet.[/red]")
    raise typer.Exit(code=2)


def _placeholder_app(name: str) -> typer.Typer:
    sub = typer.Typer(add_completion=False)

    @sub.callback(invoke_without_command=True)
    def _cb(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            console.print(f"[red]'{name}' subcommands are not implemented yet.[/red]")
            raise typer.Exit(code=2)

    return sub


app.add_typer(_placeholder_app("servers"), name="servers", help="Manage MCP servers")
app.add_typer(_placeholder_app("runtime"), name="runtime", help="Inspect runtime state")
app.add_typer(_placeholder_app("logs"), name="logs", help="View logs")
app.add_typer(_placeholder_app("config"), name="config", help="Manage configuration")


if __name__ == "__main__":
    app()
