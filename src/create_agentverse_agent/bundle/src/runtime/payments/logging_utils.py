# Copyright (c) 2026 Tejus Gupta
"""Safe logging helpers for payment wire messages."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from uagents_core.contrib.protocols.payment import RequestPayment

_REDACTED = "<redacted>"
_STRIPE_SECRET_KEYS = frozenset({"client_secret", "publishable_key"})


def sanitize_request_payment_for_log(request: RequestPayment) -> dict[str, Any]:
    """Return a log-safe dict with Stripe secrets redacted from metadata.

    Returns:
        Serializable payment payload safe for DEBUG logging.
    """
    payload = cast("dict[str, Any]", request.model_dump())
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return payload

    sanitized_metadata = copy.deepcopy(metadata)
    stripe_meta = sanitized_metadata.get("stripe")
    if isinstance(stripe_meta, dict):
        for key in _STRIPE_SECRET_KEYS:
            if key in stripe_meta:
                stripe_meta[key] = _REDACTED

    payload["metadata"] = sanitized_metadata
    return payload
