# Copyright (c) 2026 Tejus Gupta
"""Build uAgents ExternalContext for a specific inbound work item session."""

from __future__ import annotations

from uuid import UUID

from shared.db import InboundMessage
from uagents import Context
from uagents.context import ExternalContext
from uagents.types import MsgInfo


def external_context_for_inbound(
    template: Context,
    inbound: InboundMessage,
) -> ExternalContext:
    """Return a context whose session matches ``inbound``, reusing agent infra.

    Direct handlers already have the correct session on ``template``. Drain and
    other cross-session paths clone ``ExternalContext`` so outbound envelopes
    target the work item's session.

    Args:
        template: Handler context from uAgents (must be ``ExternalContext``).
        inbound: Normalized inbound work (session_id drives routing).

    Returns:
        ``template`` when sessions already match, else a new ``ExternalContext``.

    Raises:
        TypeError: When ``template`` is not an ``ExternalContext``.
    """
    if not isinstance(template, ExternalContext):
        msg = "Session routing requires ExternalContext from a message handler"
        raise TypeError(msg)

    session = UUID(inbound.session_id)
    if template.session == session:
        return template

    return ExternalContext(
        agent=template.agent,
        storage=template.storage,
        ledger=template.ledger,
        resolver=template._resolver,
        dispenser=template._dispenser,
        logger=template.logger,
        session=session,
        queries=template._queries,
        replies=template._replies,
        protocol=template._protocol,
        message_history=template._message_history,
        message_received=MsgInfo(
            message="{}",
            sender=inbound.user_id,
            schema_digest=inbound.schema_digest or "",
        ),
    )
