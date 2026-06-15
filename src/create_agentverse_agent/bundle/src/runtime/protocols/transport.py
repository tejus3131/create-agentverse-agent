# Copyright (c) 2026 Tejus Gupta
"""uAgents outbound protocol transport (production + test mock)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from uagents import Context
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.contrib.protocols.payment import (
    CompletePayment,
    RejectPayment,
    RequestPayment,
)

from runtime.protocols.cards import card_to_metadata_content
from shared.types import Resource as DevResource
from shared.types import TextReply

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from runtime.payments.service import PaymentService
    from shared.settings import Settings
    from shared.types import PaymentRequest as DevPaymentRequest


class ProtocolTransport(Protocol):
    """Outbound sends used by :class:`MessagePipeline`."""

    async def send_ack(self, recipient: str, message_id: str) -> None: ...
    async def send_text_reply(self, recipient: str, reply: TextReply) -> None: ...
    async def send_error_text(self, recipient: str, text: str) -> None: ...
    async def send_payment_request(
        self,
        *,
        recipient: str,
        user_id: str,
        session_id: str,
        message_id: str,
        request: DevPaymentRequest,
    ) -> None: ...
    async def send_complete_payment(
        self, recipient: str, transaction_id: str
    ) -> None: ...
    async def send_reject_payment(self, recipient: str, reason: str) -> None: ...
    async def send_wire_payment(
        self, recipient: str, request: RequestPayment
    ) -> None: ...


@dataclass
class MockTransport:
    """Records transport calls for unit tests."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def send_ack(self, recipient: str, message_id: str) -> None:
        self.calls.append((
            "send_ack",
            {"recipient": recipient, "message_id": message_id},
        ))

    async def send_text_reply(self, recipient: str, reply: TextReply) -> None:
        self.calls.append(("send_text_reply", {"recipient": recipient, "reply": reply}))

    async def send_error_text(self, recipient: str, text: str) -> None:
        self.calls.append(("send_error_text", {"recipient": recipient, "text": text}))

    async def send_payment_request(
        self,
        *,
        recipient: str,
        user_id: str,
        session_id: str,
        message_id: str,
        request: DevPaymentRequest,
    ) -> None:
        self.calls.append((
            "send_payment_request",
            {
                "recipient": recipient,
                "user_id": user_id,
                "session_id": session_id,
                "message_id": message_id,
                "request": request,
            },
        ))

    async def send_complete_payment(self, recipient: str, transaction_id: str) -> None:
        self.calls.append((
            "send_complete_payment",
            {"recipient": recipient, "transaction_id": transaction_id},
        ))

    async def send_reject_payment(self, recipient: str, reason: str) -> None:
        self.calls.append((
            "send_reject_payment",
            {"recipient": recipient, "reason": reason},
        ))

    async def send_wire_payment(self, recipient: str, request: RequestPayment) -> None:
        self.calls.append((
            "send_wire_payment",
            {"recipient": recipient, "request": request},
        ))


class UAgentsTransport:
    """Production transport wrapping uAgents :class:`Context`."""

    def __init__(
        self,
        ctx: Context,
        *,
        settings: Settings,
        payment_service: PaymentService,
        agent_address: str,
        agent_wallet_address: str,
    ) -> None:
        self._ctx = ctx
        self._settings = settings
        self._payment_service = payment_service
        self._agent_address = agent_address
        self._agent_wallet_address = agent_wallet_address

    async def send_ack(self, recipient: str, message_id: str) -> None:
        logger.info(
            "transport send_ack recipient=%s message_id=%s", recipient, message_id
        )
        await self._ctx.send(
            recipient,
            ChatAcknowledgement(
                timestamp=datetime.now(UTC),
                acknowledged_msg_id=UUID(message_id),
            ),
        )

    async def send_text_reply(self, recipient: str, reply: TextReply) -> None:
        logger.info(
            "transport send_text_reply recipient=%s text_len=%s resources=%s has_card=%s",
            recipient,
            len(reply.text),
            len(reply.resources) if reply.resources else 0,
            reply.card is not None,
        )
        content: list[Any] = [TextContent(type="text", text=reply.text)]
        if reply.resources:
            content.append(_resource_content(reply.resources))
        if reply.card is not None:
            content.append(card_to_metadata_content(reply.card))
        await self._ctx.send(
            recipient,
            ChatMessage(
                timestamp=datetime.now(UTC),
                msg_id=uuid4(),
                content=content,
            ),
        )

    async def send_error_text(self, recipient: str, text: str) -> None:
        logger.info(
            "transport send_error_text recipient=%s text_len=%s", recipient, len(text)
        )
        await self.send_text_reply(recipient, TextReply(text=text))

    async def send_payment_request(
        self,
        *,
        recipient: str,
        user_id: str,
        session_id: str,
        message_id: str,
        request: DevPaymentRequest,
    ) -> None:
        logger.info(
            "transport send_payment_request recipient=%s amount=%s currency=%s message_id=%s",
            recipient,
            request.amount,
            request.currency,
            message_id,
        )
        await self._payment_service.send_payment_request(
            transport=self,
            recipient=recipient,
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            request=request,
            settings=self._settings,
            agent_address=self._agent_address,
            agent_wallet_address=self._agent_wallet_address,
        )

    async def send_complete_payment(self, recipient: str, transaction_id: str) -> None:
        logger.info(
            "transport send_complete_payment recipient=%s transaction_id=%s",
            recipient,
            transaction_id,
        )
        await self._ctx.send(recipient, CompletePayment(transaction_id=transaction_id))

    async def send_reject_payment(self, recipient: str, reason: str) -> None:
        logger.info(
            "transport send_reject_payment recipient=%s reason_len=%s",
            recipient,
            len(reason),
        )
        await self._ctx.send(recipient, RejectPayment(reason=reason))

    async def send_wire_payment(self, recipient: str, request: RequestPayment) -> None:
        """Send uAgents ``RequestPayment`` wire message."""
        logger.info("transport send_wire_payment recipient=%s", recipient)
        await self._ctx.send(recipient, request)


def _resource_content(resources: list[DevResource]) -> ResourceContent:
    wire_resources: list[Resource] | Resource
    if len(resources) == 1:
        wire_resources = Resource(
            uri=resources[0].uri,
            metadata={"mime_type": resources[0].mime_type},
        )
    else:
        wire_resources = [
            Resource(uri=r.uri, metadata={"mime_type": r.mime_type}) for r in resources
        ]
    return ResourceContent(resource_id=uuid4(), resource=wire_resources)
