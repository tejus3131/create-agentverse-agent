# Copyright (c) 2026 Tejus Gupta
"""Built-in coordinator heartbeat interval handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from shared.db import AgentRuntime
    from uagents import Context


async def coordinator_tick(runtime: AgentRuntime, ctx: Context) -> None:
    """Heartbeat worker and reclaim stale coordination state.

    Drain / ``pipeline.drain_pending_work`` deferred to phase 6/7.

    Args:
        runtime: Open agent runtime coordinator.
        ctx: uAgents interval context (for logging).
    """
    result = await runtime.tick()
    reclaimed_total = (
        result.reclaimed_assigned
        + result.reclaimed_processing
        + result.reclaimed_session_locks
    )
    if reclaimed_total:
        logger.info(
            "coordinator tick reclaimed assigned=%s processing=%s session_locks=%s",
            result.reclaimed_assigned,
            result.reclaimed_processing,
            result.reclaimed_session_locks,
        )
    else:
        logger.debug(
            (
                "coordinator tick heartbeat ok reclaimed assigned=%s "
                "processing=%s session_locks=%s"
            ),
            result.reclaimed_assigned,
            result.reclaimed_processing,
            result.reclaimed_session_locks,
        )
