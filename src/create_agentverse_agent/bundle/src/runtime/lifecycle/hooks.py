# Copyright (c) 2026 Tejus Gupta
"""Invoke developer lifecycle hooks (sync or async)."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable[..., object])


async def run_hooks[T: Callable[..., object]](
    hooks: list[T],
    *,
    reverse: bool = False,
) -> None:
    """Run startup or shutdown hooks in order (or reverse for shutdown).

    Args:
        hooks: Callable hooks with no required arguments.
        reverse: When true, run hooks in reverse order (shutdown).
    """
    ordered = reversed(hooks) if reverse else hooks
    direction = "shutdown" if reverse else "startup"
    for index, hook in enumerate(ordered):
        hook_name = getattr(hook, "__name__", repr(hook))
        logger.info(
            "hook %s step=%s/%s name=%s", direction, index + 1, len(hooks), hook_name
        )
        if inspect.iscoroutinefunction(hook):
            await hook()
        else:
            hook()
        logger.debug("hook %s done name=%s", direction, hook_name)
