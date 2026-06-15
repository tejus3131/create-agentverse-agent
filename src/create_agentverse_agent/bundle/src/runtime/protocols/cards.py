# Copyright (c) 2026 Tejus Gupta
"""Build uAgents chat content blocks from developer card models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uagents_core.contrib.protocols.chat import MetadataContent
from uagents_core.contrib.protocols.chat.cards import (
    create_card_content,
    extract_card_response,
)

if TYPE_CHECKING:
    from shared.types import OutboundCard


def card_to_metadata_content(card: OutboundCard) -> MetadataContent:
    """Map :class:`OutboundCard` to uAgents ``MetadataContent``.

    Uses the official ``create_card_content`` helper so wire metadata includes
    ``requires_card_interaction``, ``card_kind``, ``card_payload``, etc.

    Args:
        card: Developer card wrapper with typed payload.

    Returns:
        Wire-format metadata block for ``ChatMessage.content``.
    """
    return create_card_content(
        card.payload,
        card_id=card.card_id,
        is_terminal=card.is_terminal,
        preferred_drawer_width_px=card.preferred_drawer_width_px,
    )


def try_parse_card_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Extract card selection from inbound ``MetadataContent`` metadata if present.

    Uses ``extract_card_response`` from uAgents card helpers.

    Returns:
        Dict suitable for ``CardSelection.model_validate`` (``values``, ``card_id``,
        ``cancelled``, ``text``), or ``None``.
    """
    response = extract_card_response(MetadataContent(metadata=metadata))
    if response is None:
        return None

    if response.selection is None and not response.cancelled and response.text is None:
        return None

    result: dict[str, Any] = {
        "values": response.selection or {},
    }
    if response.card_id is not None:
        result["card_id"] = response.card_id
    if response.cancelled:
        result["cancelled"] = True
    if response.text is not None:
        result["text"] = response.text
    return result
