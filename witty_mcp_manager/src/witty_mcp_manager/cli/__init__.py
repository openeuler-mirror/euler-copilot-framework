"""
CLI package for Witty MCP Manager.

The console entrypoint is configured in `pyproject.toml` as:

- `witty-mcp = witty_mcp_manager.cli.main:app`

This package intentionally keeps CLI wiring separated from the core modules so the
core can be imported by other processes (e.g. framework) without pulling CLI deps.
"""
