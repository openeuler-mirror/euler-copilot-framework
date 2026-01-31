"""
Module entrypoint: `python -m witty_mcp_manager`.

This delegates to the `witty-mcp` CLI.
"""

from __future__ import annotations

from witty_mcp_manager.cli.main import app


def main() -> None:
    """Entrypoint for `python -m witty_mcp_manager`."""
    app()


if __name__ == "__main__":
    main()
