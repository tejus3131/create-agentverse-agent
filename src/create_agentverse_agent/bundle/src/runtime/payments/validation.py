# Copyright (c) 2026 Tejus Gupta
"""Payment commit validation helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uagents_core.contrib.protocols.payment import Funds

    from runtime.payments.types import ActivePayment

_AMOUNT_TOLERANCE = Decimal("0.01")


def _normalize_payment_method(method: str) -> str:
    normalized = method.strip().lower()
    if normalized == "fet":
        return "fet_direct"
    return normalized


def verify_commit_funds(funds: Funds, active: ActivePayment) -> str | None:
    """Return error when commit funds do not match the active payment.

    Returns:
        Error message on mismatch, else ``None``.
    """
    if (
        "amount" not in active
        or "currency" not in active
        or "payment_method" not in active
    ):
        return None

    try:
        committed_amount = Decimal(str(funds.amount))
    except (InvalidOperation, ValueError):
        return "Invalid payment amount in commit."

    expected_amount = active["amount"]
    if abs(committed_amount - expected_amount) > _AMOUNT_TOLERANCE:
        return (
            f"Payment amount mismatch: expected {expected_amount} "
            f"{active['currency']}, got {funds.amount} {funds.currency}."
        )

    if funds.currency.upper() != active["currency"].upper():
        return (
            f"Payment currency mismatch: expected {active['currency']}, "
            f"got {funds.currency}."
        )

    if _normalize_payment_method(funds.payment_method) != _normalize_payment_method(
        active["payment_method"]
    ):
        return (
            f"Payment method mismatch: expected {active['payment_method']}, "
            f"got {funds.payment_method}."
        )

    return None
