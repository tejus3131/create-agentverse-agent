"""Initialize the create_agentverse_agent package."""

from importlib.metadata import version

from .core import greet


def main() -> None:
    """Main function to run the create_agentverse_agent package."""
    print(greet())


__all__ = ["greet"]
__version__ = version("create-agentverse-agent")
