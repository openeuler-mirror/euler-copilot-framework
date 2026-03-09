"""`witty-mcp` command line interface."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from witty_mcp_manager import __version__

# Import subcommands
from . import config as config_cmd
from . import configure as configure_cmd
from . import logs as logs_cmd
from . import runtime as runtime_cmd
from . import servers as servers_cmd

console = Console()
app = typer.Typer(add_completion=False, help="Witty MCP Manager CLI")

# Add subcommands
app.add_typer(servers_cmd.app, name="servers", help="Manage MCP servers")
app.add_typer(runtime_cmd.app, name="runtime", help="Inspect runtime state")
app.add_typer(logs_cmd.app, name="logs", help="View logs")
app.add_typer(config_cmd.app, name="config", help="Manage configuration")
app.add_typer(configure_cmd.app, name="configure", help="Configure MCP credentials")


@app.command()
def version() -> None:
    """Print the version."""
    console.print(__version__)


@app.command()
def daemon(
    debug: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--debug", help="Enable debug logging"),
    ] = False,
) -> None:
    """Run the daemon process."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("witty_mcp_manager")

    from witty_mcp_manager.config.config import load_config  # noqa: PLC0415
    from witty_mcp_manager.diagnostics.checker import Checker  # noqa: PLC0415
    from witty_mcp_manager.ipc.server import IPCServer, IPCServerConfig  # noqa: PLC0415
    from witty_mcp_manager.overlay.resolver import OverlayResolver  # noqa: PLC0415
    from witty_mcp_manager.overlay.storage import OverlayStorage  # noqa: PLC0415
    from witty_mcp_manager.registry.discovery import Discovery  # noqa: PLC0415
    from witty_mcp_manager.runtime.manager import RuntimeManager  # noqa: PLC0415

    logger.info("Starting Witty MCP Manager daemon...")

    try:
        config = load_config()
        logger.info("Configuration loaded from %s", config.socket_path)

        # Ensure required directories exist
        runtime_dir = Path(config.runtime_directory)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured runtime directory: %s", runtime_dir)

        state_dir = Path(config.state_directory)
        state_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured state directory: %s", state_dir)

        # Remove stale socket if it exists
        socket_path = Path(config.socket_path)
        if socket_path.exists():
            logger.info("Removing stale socket: %s", socket_path)
            socket_path.unlink()

        discovery = Discovery(config)
        checker = Checker()
        overlay_storage = OverlayStorage(config.state_directory)
        overlay_resolver = OverlayResolver(overlay_storage)
        runtime_manager = RuntimeManager()

        server_config = IPCServerConfig(
            config=config,
            discovery=discovery,
            checker=checker,
            overlay_storage=overlay_storage,
            overlay_resolver=overlay_resolver,
            runtime_manager=runtime_manager,
        )

        ipc_server = IPCServer(server_config)

        def signal_handler(_sig: int, _frame: object) -> None:
            logger.info("Received shutdown signal, stopping...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        import uvicorn  # noqa: PLC0415

        logger.info("Starting UDS HTTP server on %s", config.socket_path)
        uvicorn.run(
            ipc_server.app,
            uds=config.socket_path,
            log_level="debug" if debug else "info",
        )

    except Exception:
        logger.exception("Failed to start daemon")
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
