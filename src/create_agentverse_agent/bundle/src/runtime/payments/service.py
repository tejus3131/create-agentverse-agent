# Copyright (c) 2026 Tejus Gupta
"""Payment orchestration: checkout creation, verify, outbox, active payment state."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from runtime.payments.config import methods_from_settings
from runtime.payments.manager import create_payment_request, verify_payment
from runtime.payments.types import (
    PaymentContext,
    PaymentData,
    active_payment_from_storage,
    active_payment_to_storage,
)
from runtime.payments.validation import verify_commit_funds

if TYPE_CHECKING:
    from uagents_core.contrib.protocols.payment import CommitPayment, Funds

    from runtime.protocols.transport import ProtocolTransport
    from shared.db import AgentRuntime
    from shared.settings import Settings
    from shared.types import PaymentRequest as DevPaymentRequest

logger = logging.getLogger(__name__)


class PaymentService:
    """Runtime-managed payments — dev handlers only see simple request/update types."""

    def __init__(self, runtime: AgentRuntime) -> None:
        """Bind payment orchestration to a running agent runtime."""
        self._runtime = runtime

    async def send_payment_request(
        self,
        *,
        transport: ProtocolTransport,
        recipient: str,
        user_id: str,
        session_id: str,
        message_id: str,
        request: DevPaymentRequest,
        settings: Settings,
        agent_address: str,
        agent_wallet_address: str,
    ) -> None:
        """Create provider checkout, store active payment, send ``RequestPayment``."""
        methods = methods_from_settings(settings)
        idempotency_key = f"{user_id}:{session_id}|message_id:{message_id}"

        payment_data: PaymentData = {
            "amount": Decimal(str(request.amount)),
            "currency": request.currency,
            "description": request.description,
            "service": request.service,
            "product_name": request.product_name,
            "agent_name": settings.agent.name,
            "idempotency_key": idempotency_key,
        }

        context = PaymentContext(
            network=settings.runtime.network,
            logger=logger,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            agent_address=agent_address,
            wallet_address=agent_wallet_address,
            fet_lcd_url=settings.fet_lcd_url(),
        )

        wire_request, active = create_payment_request(
            data=payment_data,
            context=context,
            methods=methods,
        )

        await self._runtime.state.set_active_payment(
            user_id,
            session_id,
            active_payment_to_storage(active),
        )

        await transport.send_wire_payment(recipient, wire_request)

    async def verify_commit(
        self,
        *,
        msg: CommitPayment,
        user_id: str,
        session_id: str,
        settings: Settings,
        agent_address: str,
        agent_wallet_address: str,
    ) -> tuple[bool, str | None, str | None]:
        """Verify ``CommitPayment`` with outbox guard.

        Returns:
            ``(approved, reason, transaction_id)``
        """
        active_raw = await self._runtime.state.get_active_payment(user_id, session_id)
        if active_raw is None:
            return (
                False,
                "No active payment request for this session.",
                msg.transaction_id,
            )

        active = active_payment_from_storage(active_raw)
        message_id = active["message_id"]
        side_effect_key = f"payment:{message_id}"

        if await self._runtime.coordinator.has_side_effect(side_effect_key):
            return True, None, msg.transaction_id

        context = PaymentContext(
            network=settings.runtime.network,
            logger=logger,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            agent_address=agent_address,
            wallet_address=agent_wallet_address,
            fet_lcd_url=settings.fet_lcd_url(),
        )
        methods = methods_from_settings(settings)
        funds: Funds = msg.funds

        funds_error = verify_commit_funds(funds, active)
        if funds_error is not None:
            return False, funds_error, msg.transaction_id

        result = await verify_payment(
            transaction_id=msg.transaction_id,
            funds=funds,
            context=context,
            methods=methods,
            payment_information=active,
        )

        if result["verified"]:
            await self._runtime.coordinator.record_side_effect(
                message_id=message_id,
                effect_type="payment_charge",
                idempotency_key=side_effect_key,
                payload_json={
                    "transaction_id": msg.transaction_id,
                    "method": funds.payment_method,
                },
            )
            return True, None, msg.transaction_id

        return (
            False,
            result.get("error") or "Payment verification failed.",
            msg.transaction_id,
        )
