"""
Template renderer for CLI output.

This module provides a centralized template rendering system for CLI output,
replacing scattered console.print() calls with maintainable Jinja2 templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from rich.console import Console

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Global Jinja2 environment
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Get or create Jinja2 environment."""
    global _jinja_env  # noqa: PLW0603
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(disabled_extensions=("txt",)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Register custom filters
        _jinja_env.filters["format_duration"] = _format_duration
    return _jinja_env


def _format_duration(seconds: int | None) -> str:
    """Format duration in seconds to human-readable format."""
    if seconds is None:
        return "N/A"
    remaining = int(seconds)
    minutes, sec = divmod(remaining, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {sec}s"
    if minutes > 0:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """
    Render a template with the given context.

    Args:
        template_name: Name of the template file (e.g., 'daemon_status.txt')
        context: Dictionary of variables to pass to the template

    Returns:
        Rendered template string

    """
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)


def print_template(
    console: Console,
    template_name: str,
    context: dict[str, Any],
) -> None:
    """
    Render and print a template to console.

    Args:
        console: Rich Console instance
        template_name: Name of the template file
        context: Dictionary of variables to pass to the template

    """
    output = render_template(template_name, context)
    console.print(output, end="")
