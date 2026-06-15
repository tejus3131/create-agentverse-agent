# Copyright (c) 2026 Tejus Gupta
"""Payment commit validation helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uagents_core.contrib.protocols.payment import Funds

    from runtime.payments.types import AcceptedFund, ActivePayment

_AMOUNT_TOLERANCE = Decimal("0.01")


def _normalize_payment_method(method: str) -> str:
    normalized = method.strip().lower()
    if normalized == "fet":
        return "fet_direct"
    return normalized


def _find_accepted_fund(
    funds: Funds, accepted_funds: list[AcceptedFund]
) -> AcceptedFund | None:
    normalized_commit = _normalize_payment_method(funds.payment_method)
    for entry in accepted_funds:
        if _normalize_payment_method(entry["payment_method"]) == normalized_commit:
            return entry
    return None


def verify_commit_funds(funds: Funds, active: ActivePayment) -> str | None:
    """Return error when commit funds do not match the active payment.

    When multiple payment methods were offered, the commit must match one of the
    stored ``accepted_funds`` entries (amount, currency, and method).

    Returns:
        Error message on mismatch, else ``None``.
    """
    accepted_funds = active.get("accepted_funds")
    if accepted_funds:
        matched = _find_accepted_fund(funds, accepted_funds)
        if matched is None:
            return (
                f"Payment method mismatch: not among accepted methods, "
                f"got {funds.payment_method}."
            )
        expected_amount = Decimal(str(matched["amount"]))
        expected_currency = matched["currency"]
    elif (
        "amount" in active
        and "currency" in active
        and "payment_method" in active
    ):
        expected_amount = active["amount"]
        expected_currency = active["currency"]
        if _normalize_payment_method(funds.payment_method) != _normalize_payment_method(
            active["payment_method"]
        ):
            return (
                f"Payment method mismatch: expected {active['payment_method']}, "
                f"got {funds.payment_method}."
            )
    else:
        return None

    try:
        committed_amount = Decimal(str(funds.amount))
    except (InvalidOperation, ValueError):
        return "Invalid payment amount in commit."

    if abs(committed_amount - expected_amount) > _AMOUNT_TOLERANCE:
        return (
            f"Payment amount mismatch: expected {expected_amount} "
            f"{expected_currency}, got {funds.amount} {funds.currency}."
        )

    if funds.currency.upper() != expected_currency.upper():
        return (
            f"Payment currency mismatch: expected {expected_currency}, "
            f"got {funds.currency}."
        )

    return None
