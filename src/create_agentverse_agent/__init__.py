"""Initialize the create_agentverse_agent package."""

from importlib.metadata import version

from .cli import app


def main() -> None:
    """Main entry point for CLI."""
    app()


__all__ = ["main"]
__version__ = version("create-agentverse-agent")
