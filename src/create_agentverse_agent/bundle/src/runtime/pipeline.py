# Copyright (c) 2026 Tejus Gupta
"""Message pipeline: coordination → ack → handler → response → finish → drain."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, Any

from runtime.payload import payload_to_handler_request
from runtime.protocols.session_context import external_context_for_inbound
from runtime.protocols.transport import UAgentsTransport
from shared.db import (
    AgentRuntime,
    ClaimDecision,
    ProcessStage,
    is_deferred_ack,
    is_payment_followup,
    is_policy_reject,
    is_silent_skip,
)
from shared.types import PaymentRequest, TextReply

if TYPE_CHECKING:
    from uagents import Context

    from runtime.payments.service import PaymentService
    from runtime.protocols.transport import ProtocolTransport
    from shared.db import (
        InboundMessage,
    )
    from shared.settings import Settings
    from shared.types import AgentDefinition, HandlerResponse, MessageHandler

logger = logging.getLogger(__name__)

_POLICY_MESSAGES: dict[ProcessStage, str] = {
    ProcessStage.ACL: "You are not authorized to use this agent.",
    ProcessStage.PAYMENT_GATE: (
        "Payment is still pending for this session. "
        "Please complete or reject payment to continue."
    ),
    ProcessStage.RATE_LIMIT: "Rate limit exceeded. Please try again later.",
}

_GENERIC_ERROR = "Something went wrong on my side. Please try again in a moment."


class MessagePipeline:
    """Orchestrates inbound work through Postgres coordination and dev handlers."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        definition: AgentDefinition,
        settings: Settings,
        payment_service: PaymentService,
        agent_address: str,
        agent_wallet_address: str,
    ) -> None:
        self._runtime = runtime
        self._handler = definition.on_message
        self._settings = settings
        self._payment_service = payment_service
        self._agent_address = agent_address
        self._agent_wallet_address = agent_wallet_address

    def transport_for(self, ctx: Context) -> ProtocolTransport:
        """Build production transport for a uAgents context."""
        return UAgentsTransport(
            ctx,
            settings=self._settings,
            payment_service=self._payment_service,
            agent_address=self._agent_address,
            agent_wallet_address=self._agent_wallet_address,
        )

    async def process_inbound(
        self,
        ctx: Context,
        _sender: str,
        inbound: InboundMessage,
        *,
        transport: ProtocolTransport | None = None,
    ) -> None:
        """Run full inbound flow for one work item.

        Args:
            ctx: uAgents context.
            _sender: Peer address from handler (``inbound.user_id`` used for sends).
            inbound: Normalized inbound message.
            transport: Optional transport override (for tests).
        """
        logger.info(
            "pipeline begin message_id=%s user_id=%s session_id=%s protocol=%s",
            inbound.message_id,
            inbound.user_id,
            inbound.session_id,
            inbound.protocol,
        )
        logger.debug("pipeline step=coordination payload=%s", inbound.payload_json)

        result = await self._runtime.process_inbound(inbound)
        logger.info(
            "pipeline step=coordination result stage=%s decision=%s",
            result.stage,
            result.decision,
        )

        effective_ctx = external_context_for_inbound(ctx, inbound)
        recipient = inbound.user_id
        tx = transport or self.transport_for(effective_ctx)

        payment_followup = is_payment_followup(result, inbound)

        if is_deferred_ack(result):
            logger.info("pipeline step=deferred_ack message_id=%s", inbound.message_id)
            await tx.send_ack(recipient, inbound.message_id)

        if is_silent_skip(result) and not payment_followup:
            logger.info(
                "pipeline end silent_skip message_id=%s stage=%s",
                inbound.message_id,
                result.stage,
            )
            return

        if payment_followup:
            await self._run_payment_followup(
                tx,
                recipient=recipient,
                inbound=inbound,
            )
            return

        if is_policy_reject(result):
            message = _POLICY_MESSAGES.get(
                result.stage,
                "Request could not be processed.",
            )
            logger.info(
                "pipeline step=policy_reject message_id=%s stage=%s",
                inbound.message_id,
                result.stage,
            )
            await tx.send_error_text(recipient, message)
            logger.info("pipeline end policy_reject message_id=%s", inbound.message_id)
            await self._drain_once(ctx)
            return

        if result.stage is not ProcessStage.READY:
            logger.warning(
                "pipeline end unexpected_stage message_id=%s stage=%s decision=%s",
                inbound.message_id,
                result.stage,
                result.decision,
            )
            return

        logger.info("pipeline step=send_ack message_id=%s", inbound.message_id)
        await tx.send_ack(recipient, inbound.message_id)

        logger.info("pipeline step=parse_payload message_id=%s", inbound.message_id)
        request = payload_to_handler_request(inbound.protocol, inbound.payload_json)
        logger.debug("pipeline step=handler_request type=%s", type(request).__name__)

        try:
            logger.info(
                "pipeline step=invoke_handler message_id=%s", inbound.message_id
            )
            response = await _invoke_handler(
                self._handler,
                user_id=inbound.user_id,
                session_id=inbound.session_id,
                message_id=inbound.message_id,
                request=request,
            )
            logger.info(
                "pipeline step=handler_done message_id=%s response_type=%s",
                inbound.message_id,
                type(response).__name__,
            )
            logger.info(
                "pipeline step=deliver_response message_id=%s", inbound.message_id
            )
            await self._deliver_response(
                tx,
                recipient=recipient,
                inbound=inbound,
                response=response,
            )
            logger.info(
                "pipeline step=finish_processing success message_id=%s",
                inbound.message_id,
            )
            status = await self._runtime.finish_processing(
                message_id=inbound.message_id,
                user_id=inbound.user_id,
                session_id=inbound.session_id,
                success=True,
            )
            logger.info(
                "pipeline step=finish_processing done message_id=%s status=%s",
                inbound.message_id,
                status,
            )
        except Exception:
            logger.exception(
                "pipeline step=handler_failed message_id=%s user=%s session=%s",
                inbound.message_id,
                inbound.user_id,
                inbound.session_id,
            )
            status = await self._runtime.finish_processing(
                message_id=inbound.message_id,
                user_id=inbound.user_id,
                session_id=inbound.session_id,
                success=False,
                error_reason="handler_error",
            )
            logger.info(
                "pipeline step=finish_processing failed message_id=%s status=%s",
                inbound.message_id,
                status,
            )
            await tx.send_error_text(recipient, _GENERIC_ERROR)
            await self._drain_once(ctx)
            return

        logger.info("pipeline step=drain_once message_id=%s", inbound.message_id)
        await self._drain_once(ctx)
        logger.info("pipeline end success message_id=%s", inbound.message_id)

    async def _run_payment_followup(
        self,
        transport: ProtocolTransport,
        *,
        recipient: str,
        inbound: InboundMessage,
    ) -> None:
        """Invoke dev handler after payment verify/reject (post-chat terminal item)."""
        logger.info("pipeline step=payment_followup message_id=%s", inbound.message_id)
        await transport.send_ack(recipient, inbound.message_id)
        request = payload_to_handler_request(inbound.protocol, inbound.payload_json)
        logger.debug("pipeline step=handler_request type=%s", type(request).__name__)
        try:
            logger.info(
                "pipeline step=invoke_handler message_id=%s", inbound.message_id
            )
            response = await _invoke_handler(
                self._handler,
                user_id=inbound.user_id,
                session_id=inbound.session_id,
                message_id=inbound.message_id,
                request=request,
            )
            logger.info(
                "pipeline step=handler_done message_id=%s response_type=%s",
                inbound.message_id,
                type(response).__name__,
            )
            logger.info(
                "pipeline step=deliver_response message_id=%s", inbound.message_id
            )
            await self._deliver_response(
                transport,
                recipient=recipient,
                inbound=inbound,
                response=response,
            )
        except Exception:
            logger.exception(
                "pipeline step=payment_followup_failed message_id=%s user=%s session=%s",
                inbound.message_id,
                inbound.user_id,
                inbound.session_id,
            )
            await transport.send_error_text(recipient, _GENERIC_ERROR)
            return
        logger.info("pipeline end payment_followup message_id=%s", inbound.message_id)

    async def _deliver_response(
        self,
        transport: ProtocolTransport,
        *,
        recipient: str,
        inbound: InboundMessage,
        response: HandlerResponse,
    ) -> None:
        if isinstance(response, TextReply):
            logger.debug(
                "deliver text_reply recipient=%s text_len=%s has_card=%s",
                recipient,
                len(response.text),
                response.card is not None,
            )
            await transport.send_text_reply(recipient, response)
            return
        if isinstance(response, PaymentRequest):
            logger.debug(
                "deliver payment_request recipient=%s amount=%s currency=%s",
                recipient,
                response.amount,
                response.currency,
            )
            await transport.send_payment_request(
                recipient=recipient,
                user_id=inbound.user_id,
                session_id=inbound.session_id,
                message_id=inbound.message_id,
                request=response,
            )
            return
        msg = f"Unsupported handler response type: {type(response)!r}"
        raise TypeError(msg)

    async def _drain_once(self, ctx: Context) -> None:
        logger.debug("drain_once begin")
        claim = await self._runtime.drain_once()
        if claim.work_item is None:
            logger.debug("drain_once empty")
            return
        if claim.decision is not ClaimDecision.CLAIMED:
            logger.info(
                "drain_once skipped decision=%s message_id=%s",
                claim.decision,
                claim.work_item.message_id if claim.work_item else None,
            )
            return
        inbound = AgentRuntime.inbound_from_work_item(claim.work_item)
        logger.info(
            "drain_once claimed message_id=%s protocol=%s",
            inbound.message_id,
            inbound.protocol,
        )
        await self.process_inbound(ctx, inbound.user_id, inbound)


async def _invoke_handler(
    handler: MessageHandler,
    *,
    user_id: str,
    session_id: str,
    message_id: str,
    request: Any,
) -> HandlerResponse:
    kwargs = {
        "user_id": user_id,
        "session_id": session_id,
        "message_id": message_id,
        "request": request,
    }
    if inspect.iscoroutinefunction(handler):
        logger.debug("invoke_handler async message_id=%s", message_id)
        return await handler(**kwargs)
    logger.debug("invoke_handler sync thread message_id=%s", message_id)
    return await asyncio.to_thread(handler, **kwargs)
