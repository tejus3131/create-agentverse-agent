# Copyright (c) 2026 Tejus Gupta
"""Main module."""

import asyncio

from agent import definition
from runtime.agent import AgentRunner


def main() -> None:
    """Main function."""
    runner = AgentRunner.from_definition(definition)
    asyncio.run(runner.preflight())
    runner.run()
