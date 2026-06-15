# Copyright (c) 2026 Tejus Gupta
"""Map coordination payload_json to developer handler types."""

from __future__ import annotations

from typing import Any

from shared.types import (
    CardSelection,
    ChatInput,
    HandlerRequest,
    PaymentUpdate,
    Resource,
    parse_card_selection_text,
)


def payload_to_handler_request(
    protocol: str,
    payload_json: dict[str, Any],
) -> HandlerRequest:
    """Convert stored inbound payload to :class:`HandlerRequest`.

    Args:
        protocol: ``chat`` or ``payment``.
        payload_json: JSON from :class:`InboundMessage`.

    Returns:
        Developer-facing request model.

    Raises:
        ValueError: Unknown protocol or invalid payload.
    """
    if protocol == "chat":
        return _chat_payload(payload_json)
    if protocol == "payment":
        return _payment_payload(payload_json)
    msg = f"Unsupported protocol: {protocol}"
    raise ValueError(msg)


def _chat_payload(payload_json: dict[str, Any]) -> ChatInput:
    text = payload_json.get("text")
    text_str = str(text).strip() if text is not None else None
    if text_str is not None and not text_str:
        text_str = None

    resources_raw = payload_json.get("resources")
    resources: list[Resource] | None = None
    if isinstance(resources_raw, list) and resources_raw:
        resources = [Resource.model_validate(item) for item in resources_raw]

    card_raw = payload_json.get("card_selection")
    card_selection: CardSelection | None = None
    if isinstance(card_raw, dict):
        card_selection = CardSelection.model_validate(card_raw)
    elif text_str:
        card_selection = parse_card_selection_text(text_str)

    return ChatInput(text=text_str, resources=resources, card_selection=card_selection)


def _payment_payload(payload_json: dict[str, Any]) -> PaymentUpdate:
    approved = bool(payload_json.get("payment_approved"))
    reason = payload_json.get("reason")
    transaction_id = payload_json.get("transaction_id")
    return PaymentUpdate(
        approved=approved,
        reason=str(reason) if reason is not None else None,
        transaction_id=str(transaction_id) if transaction_id is not None else None,
    )


def chat_payload_from_message(
    *,
    text: str,
    resources: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build ``payload_json`` for chat protocol inbound work.

    Returns:
        Chat inbound payload mapping.
    """
    payload: dict[str, Any] = {"text": text}
    if resources:
        payload["resources"] = resources
    return payload


def payment_payload_from_outcome(
    *,
    payment_approved: bool,
    reason: str | None = None,
    transaction_id: str | None = None,
) -> dict[str, Any]:
    """Build ``payload_json`` for payment protocol inbound work.

    Returns:
        Payment inbound payload mapping.
    """
    payload: dict[str, Any] = {"payment_approved": payment_approved}
    if reason is not None:
        payload["reason"] = reason
    if transaction_id is not None:
        payload["transaction_id"] = transaction_id
    return payload
