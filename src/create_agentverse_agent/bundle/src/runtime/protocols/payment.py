# Copyright (c) 2026 Tejus Gupta
"""Payment protocol — verify externally, route outcomes through pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    RejectPayment,
    payment_protocol_spec,
)

from runtime.payload import payment_payload_from_outcome
from shared.db import InboundMessage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from runtime.agent import AgentRunner


def setup_payment_protocol(runner: AgentRunner) -> Protocol:
    """Wire payment protocol to verify + pipeline (not direct handler calls).

    Args:
        runner: Agent runner with pipeline and runtime.

    Returns:
        Configured uAgents payment protocol (seller role).
    """
    protocol = Protocol(spec=payment_protocol_spec, role="seller")

    @protocol.on_message(CommitPayment)
    async def on_commit_payment(ctx: Context, sender: str, msg: CommitPayment) -> None:
        session_id = str(ctx.session)
        logger.info(
            "payment commit received sender=%s session=%s transaction_id=%s",
            sender,
            session_id,
            msg.transaction_id,
        )
        if runner._pipeline is None or runner.runtime is None:  # noqa: SLF001
            logger.error(
                "payment commit dropped — preflight not complete sender=%s",
                sender,
            )
            return
        runtime = runner.runtime
        active = await runtime.state.get_active_payment(sender, session_id)
        if active is None:
            ctx.logger.warning("CommitPayment with no active payment sender=%s", sender)
            transport = runner.pipeline.transport_for(ctx)
            await transport.send_reject_payment(
                sender,
                "No active payment request for this session.",
            )
            return

        payment_service = runner.payment_service
        if payment_service is None:
            ctx.logger.error("Payment service not initialized")
            return

        approved, reason, transaction_id = await payment_service.verify_commit(
            msg=msg,
            user_id=sender,
            session_id=session_id,
            settings=runner.settings,
            agent_address=runner.agent.address,
            agent_wallet_address=str(runner.agent.wallet.address()),
        )
        logger.info(
            "payment commit verified sender=%s approved=%s transaction_id=%s",
            sender,
            approved,
            transaction_id,
        )

        transport = runner.pipeline.transport_for(ctx)
        if approved:
            await transport.send_complete_payment(sender, msg.transaction_id)
        else:
            await transport.send_reject_payment(
                sender,
                reason or "Payment verification failed.",
            )

        message_id = str(active["message_id"])
        inbound = InboundMessage(
            message_id=message_id,
            user_id=sender,
            session_id=session_id,
            protocol="payment",
            payload_json=payment_payload_from_outcome(
                payment_approved=approved,
                reason=reason,
                transaction_id=transaction_id,
            ),
        )
        logger.info(
            "payment dispatch pipeline message_id=%s approved=%s", message_id, approved
        )
        await runner.pipeline.process_inbound(ctx, sender, inbound)
        await runtime.state.remove_active_payment(sender, session_id)
        logger.info("payment commit done sender=%s message_id=%s", sender, message_id)

    @protocol.on_message(RejectPayment)
    async def on_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
        session_id = str(ctx.session)
        logger.info(
            "payment reject received sender=%s session=%s reason=%s",
            sender,
            session_id,
            msg.reason,
        )
        if runner._pipeline is None or runner.runtime is None:  # noqa: SLF001
            logger.error(
                "payment reject dropped — preflight not complete sender=%s",
                sender,
            )
            return
        runtime = runner.runtime

        active = await runtime.state.get_active_payment(sender, session_id)
        if active is None:
            ctx.logger.warning("RejectPayment with no active payment sender=%s", sender)
            return

        message_id = str(active["message_id"])
        inbound = InboundMessage(
            message_id=message_id,
            user_id=sender,
            session_id=session_id,
            protocol="payment",
            payload_json=payment_payload_from_outcome(
                payment_approved=False,
                reason=msg.reason or "Payment rejected by user.",
            ),
        )
        logger.info(
            "payment dispatch pipeline message_id=%s approved=false", message_id
        )
        await runner.pipeline.process_inbound(ctx, sender, inbound)
        await runtime.state.remove_active_payment(sender, session_id)
        logger.info("payment reject done sender=%s message_id=%s", sender, message_id)

    return protocol
