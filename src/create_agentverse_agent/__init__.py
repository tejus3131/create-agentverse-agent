"""Initialize the create_agentverse_agent package."""

from importlib.metadata import version

from .core import greet

__all__ = ["greet"]
__version__ = version("create-agentverse-agent")
