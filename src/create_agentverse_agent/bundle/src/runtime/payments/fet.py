# Copyright (c) 2026 Tejus Gupta
"""Production-ready FET blockchain payment verification.

This module provides utilities for verifying FET (Fetch.ai) blockchain payments
by querying the LCD (Light Client Daemon) endpoint and validating transaction
details including recipient address and amount.

The verification process includes:
    1. Fetching transaction data from the FET LCD endpoint
    2. Checking transaction execution status (success/failure)
    3. Verifying payment details via transaction messages
    4. Fallback verification via transaction events

Key Functions:
    verify_fet_payment: Main entry point for FET payment verification.

Internal Helpers:
    _amounts_match: Compare amounts with tolerance.
    _parse_amount: Parse atomic amount strings.
    _match_via_messages: Check transaction messages for payment.
    _match_via_events: Check transaction events for payment.
    _verify_transaction_details: Orchestrate message/event verification.
    _check_transaction_status: Validate transaction execution code.
    _fetch_transaction: Fetch transaction with retries.

Examples:
    Basic usage::

        from setup.payments.fet import verify_fet_payment

        result = await verify_fet_payment(
            transaction_id="ABC123...",
            wallet_address="fetch1abc...",
            payment_information=active_payment,
            context=payment_context,
        )

        if result["verified"]:
            print("Payment verified successfully")
        else:
            print(f"Verification failed: {result['error']}")
"""

from __future__ import annotations

import asyncio
import math
from typing import cast

import httpx

from runtime.payments.constants import (
    FET_DENOM_SCALE,
    FET_VERIFY_ATTEMPTS,
    FET_VERIFY_DELAY_SEC,
    HTTP_STATUS_OK,
)
from runtime.payments.types import (
    ActivePayment,
    PaymentContext,
    TransactionData,
    TransactionEvent,
    VerificationResult,
)

__all__ = ["verify_fet_payment"]


# =============================================================================
# Amount Comparison Utilities
# =============================================================================


def _amounts_match(
    *,
    actual: float,
    expected: float,
    context: PaymentContext,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-12,
) -> bool:
    """Check if two amounts match within tolerance.

    Uses math.isclose for floating point comparison with configurable
    relative and absolute tolerances.

    Args:
        actual: Actual amount from transaction.
        expected: Expected amount from payment request.
        context: PaymentContext for logging.
        rel_tol: Relative tolerance (default: 1e-6).
        abs_tol: Absolute tolerance (default: 1e-12).

    Returns:
        True if amounts are within tolerance.
    """
    try:
        result = math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)
    except Exception:
        context.logger.exception(
            "[PaymentUtils]: %s | %s | %s | Error comparing amounts.",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return False
    else:
        context.logger.info(
            (
                "[PaymentUtils]: %s | %s | %s | Comparing amounts. "
                "Actual: %.6f, Expected: %.6f, Match: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            actual,
            expected,
            result,
        )
        return result


# =============================================================================
# Amount Parsing
# =============================================================================


def _parse_amount(*, amount_str: str, context: PaymentContext) -> float | None:
    """Parse amount string like '1000000ufet' into numeric amount.

    Extracts numeric characters from amount strings commonly found in
    blockchain transaction data. Handles both integer and decimal formats.

    Args:
        amount_str: Amount string to parse (e.g., '1000000ufet').
        context: PaymentContext for logging.

    Returns:
        Parsed amount as float, or None if parsing fails.
    """
    try:
        num_chars: list[str] = [
            char for char in amount_str if char.isdigit() or char == "."
        ]

        if not num_chars:
            context.logger.warning(
                "[PaymentUtils]: %s | %s | %s | Failed to parse amount. Input: %s",
                context.user_id,
                context.session_id,
                context.message_id,
                amount_str,
            )
            return None

        amount = float("".join(num_chars))
    except ValueError:
        context.logger.exception(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "ValueError while parsing amount. Input: %s."
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            amount_str,
        )
        return None
    except Exception:
        context.logger.exception(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Unexpected error in parse_amount. Input: %s."
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            amount_str,
        )
        return None
    else:
        context.logger.info(
            "[PaymentUtils]: %s | %s | %s | Parsed amount: %.6f from input: %s",
            context.user_id,
            context.session_id,
            context.message_id,
            amount,
            amount_str,
        )
        return amount


# =============================================================================
# Transaction Message Verification
# =============================================================================


def _match_via_messages(
    *,
    tx_data: TransactionData,
    recipient_address: str,
    expected_amount_fet: float,
    context: PaymentContext,
) -> bool:
    """Check transaction messages for matching payment.

    Parses the transaction body to find MsgSend messages and verifies
    that the recipient address and amount match expected values.

    Args:
        tx_data: Raw transaction data from LCD endpoint.
        recipient_address: Expected recipient wallet address.
        expected_amount_fet: Expected amount in FET (not atomic units).
        context: PaymentContext for logging.

    Returns:
        True if a matching message is found.
    """
    try:
        tx = tx_data.get("tx", {})
        body = tx.get("body", {})
        messages = body.get("messages", [])

        for msg in messages:
            msg_type = msg.get("@type", "")

            if "MsgSend" not in msg_type:
                continue

            to_addr = msg.get("to_address")

            if to_addr != recipient_address:
                continue

            for coin in msg.get("amount", []):
                amount_str = coin.get("amount")

                if not amount_str:
                    continue

                try:
                    amount_atomic = float(amount_str)
                except ValueError as e:
                    context.logger.warning(
                        (
                            "[PaymentUtils]: %s | %s | %s | "
                            "ValueError while parsing amount in message. "
                            "Amount string: %s, Error: %s"
                        ),
                        context.user_id,
                        context.session_id,
                        context.message_id,
                        amount_str,
                        e,
                    )
                    continue

                amount_fet = amount_atomic / FET_DENOM_SCALE

                if _amounts_match(
                    actual=amount_fet,
                    expected=expected_amount_fet,
                    context=context,
                ):
                    context.logger.info(
                        (
                            "[PaymentUtils]: %s | %s | %s | "
                            "Match found via messages. Recipient: %s, Amount: %.6f"
                        ),
                        context.user_id,
                        context.session_id,
                        context.message_id,
                        recipient_address,
                        amount_fet,
                    )
                    return True

    except Exception:
        context.logger.exception(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Unexpected error while matching via messages."
            ),
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return False
    else:
        context.logger.info(
            (
                "[PaymentUtils]: %s | %s | %s | No match found via messages. "
                "Recipient: %s, Expected Amount: %.6f"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            recipient_address,
            expected_amount_fet,
        )
        return False


# =============================================================================
# Transaction Event Verification
# =============================================================================


def _check_event_amount_match(
    *,
    event: TransactionEvent,
    recipient_address: str,
    expected_amount_fet: float,
    context: PaymentContext,
) -> bool:
    """Check if event contains matching amount for recipient.

    Examines transaction events of type 'coin_received' or 'transfer'
    to verify payment details when message-level verification fails.

    Args:
        event: Single transaction event data.
        recipient_address: Expected recipient wallet address.
        expected_amount_fet: Expected amount in FET (not atomic units).
        context: PaymentContext for logging.

    Returns:
        True if event contains matching payment to recipient.
    """
    event_type = event.get("type", "").lower()

    if event_type not in {"coin_received", "transfer"}:
        return False

    receiver = None
    amount_raw = None

    for attr in event.get("attributes", []):
        key = attr.get("key", "").lower()
        value = attr.get("value", "")

        if key in {"receiver", "recipient"}:
            receiver = value
        elif key == "amount":
            amount_raw = value

    if receiver != recipient_address or not amount_raw:
        return False

    parts = amount_raw.split(",") if "," in amount_raw else [amount_raw]

    for part in parts:
        amount_atomic = _parse_amount(
            amount_str=part,
            context=context,
        )

        if amount_atomic is None:
            continue

        amount_fet = amount_atomic / FET_DENOM_SCALE

        if _amounts_match(
            actual=amount_fet,
            expected=expected_amount_fet,
            context=context,
        ):
            context.logger.info(
                (
                    "[PaymentUtils]: %s | %s | %s | "
                    "Match found via events. Recipient: %s, Amount: %.6f"
                ),
                context.user_id,
                context.session_id,
                context.message_id,
                recipient_address,
                amount_fet,
            )
            return True

    return False


def _match_via_events(
    *,
    tx_data: TransactionData,
    recipient_address: str,
    expected_amount_fet: float,
    context: PaymentContext,
) -> bool:
    """Check transaction events for matching payment.

    Fallback verification method that examines transaction logs and events
    when message-level verification fails. Iterates through all logs and
    their events to find matching coin_received or transfer events.

    Args:
        tx_data: Raw transaction data from LCD endpoint.
        recipient_address: Expected recipient wallet address.
        expected_amount_fet: Expected amount in FET (not atomic units).
        context: PaymentContext for logging.

    Returns:
        True if a matching event is found.
    """
    try:
        tx_response = tx_data.get("tx_response", {})
        logs = tx_response.get("logs", [])

        for log in logs:
            for event in log.get("events", []):
                if _check_event_amount_match(
                    event=event,
                    recipient_address=recipient_address,
                    expected_amount_fet=expected_amount_fet,
                    context=context,
                ):
                    return True

        context.logger.info(
            (
                "[PaymentUtils]: %s | %s | %s | No match found via events. "
                "Recipient: %s, Expected Amount: %.6f"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            recipient_address,
            expected_amount_fet,
        )
    except Exception:
        context.logger.exception(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Unexpected error while matching via events."
            ),
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return False
    else:
        return False


# =============================================================================
# Transaction Verification Orchestration
# =============================================================================


def _verify_transaction_details(
    *,
    tx_data: TransactionData,
    recipient_address: str,
    expected_amount_fet: float,
    context: PaymentContext,
) -> bool:
    """Verify transaction contains expected payment.

    Orchestrates the verification process by first attempting to verify
    via transaction messages, then falling back to event-based verification
    if message verification fails.

    Args:
        tx_data: Raw transaction data from LCD endpoint.
        recipient_address: Expected recipient wallet address.
        expected_amount_fet: Expected amount in FET (not atomic units).
        context: PaymentContext for logging.

    Returns:
        True if payment is verified via messages or events.
    """
    # Try messages first
    if _match_via_messages(
        tx_data=tx_data,
        recipient_address=recipient_address,
        expected_amount_fet=expected_amount_fet,
        context=context,
    ):
        return True

    # Fallback to events
    return _match_via_events(
        tx_data=tx_data,
        recipient_address=recipient_address,
        expected_amount_fet=expected_amount_fet,
        context=context,
    )


def _check_transaction_status(
    *, tx_data: TransactionData, context: PaymentContext
) -> bool:
    """Check if transaction executed successfully.

    Verifies the transaction response code is 0 (success). A non-zero
    code indicates the transaction failed during execution.

    Args:
        tx_data: Raw transaction data from LCD endpoint.
        context: PaymentContext for logging.

    Returns:
        True if transaction code is 0 (success).
    """
    try:
        tx_response = tx_data.get("tx_response", {})
        code = int(tx_response.get("code", 0))

        if code == 0:
            context.logger.info(
                (
                    "[PaymentUtils]: %s | %s | %s | "
                    "Transaction status verified as successful. Code: %d"
                ),
                context.user_id,
                context.session_id,
                context.message_id,
                code,
            )
            return True
    except Exception:
        context.logger.exception(
            "[PaymentUtils]: %s | %s | %s | Error checking transaction status.",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return False
    else:
        context.logger.warning(
            "[PaymentUtils]: %s | %s | %s | Transaction failed with code: %d",
            context.user_id,
            context.session_id,
            context.message_id,
            code,
        )
        return False


# =============================================================================
# LCD API Communication
# =============================================================================


async def _fetch_tx_attempt(
    *, candidate_hash: str, context: PaymentContext
) -> TransactionData | None:
    """Attempt to fetch transaction from LCD endpoint.

    Makes a single HTTP request to the FET LCD endpoint to retrieve
    transaction data by hash.

    Args:
        candidate_hash: Transaction hash to query.
        context: PaymentContext for logging.

    Returns:
        Transaction data if found, None otherwise.
    """
    url = f"{context.fet_lcd_url}/cosmos/tx/v1beta1/txs/{candidate_hash}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)

            if response.status_code == HTTP_STATUS_OK:
                context.logger.info(
                    (
                        "[PaymentUtils]: %s | %s | %s | "
                        "Transaction fetched successfully. Hash: %s"
                    ),
                    context.user_id,
                    context.session_id,
                    context.message_id,
                    candidate_hash,
                )
                return cast("TransactionData", response.json())

    except httpx.HTTPError as e:
        context.logger.warning(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "HTTP error during transaction fetch. Hash: %s, "
                "Error: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            candidate_hash,
            e,
        )

    return None


async def _fetch_transaction(
    *, tx_hash: str, context: PaymentContext
) -> TransactionData | None:
    """Fetch transaction data from LCD endpoint with retries.

    Attempts to retrieve transaction data with configurable retry logic.
    Tries both the original hash and lowercase variant to handle case
    sensitivity issues across different systems.

    Args:
        tx_hash: Transaction hash to fetch.
        context: PaymentContext for logging.

    Returns:
        Transaction data if found after retries, None otherwise.

    Note:
        Uses FET_VERIFY_ATTEMPTS and FET_VERIFY_DELAY_SEC constants
        for retry configuration.
    """
    try:
        candidates = [tx_hash, tx_hash.lower()]

        for attempt in range(1, FET_VERIFY_ATTEMPTS + 1):
            for candidate_hash in candidates:
                tx_data = await _fetch_tx_attempt(
                    candidate_hash=candidate_hash,
                    context=context,
                )
                if tx_data is not None:
                    return tx_data

            if attempt < FET_VERIFY_ATTEMPTS:
                context.logger.info(
                    (
                        "[PaymentUtils]: %s | %s | %s | "
                        "Transaction not found yet. Attempt %d/%d. "
                        "Retrying after delay..."
                    ),
                    context.user_id,
                    context.session_id,
                    context.message_id,
                    attempt,
                    FET_VERIFY_ATTEMPTS,
                )
                await asyncio.sleep(FET_VERIFY_DELAY_SEC)
    except Exception:
        context.logger.exception(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Error fetching transaction data after all attempts. Hash: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            tx_hash,
        )
        return None
    else:
        context.logger.error(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Transaction not found after all attempts. Hash: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            tx_hash,
        )
        return None


# =============================================================================
# Public API
# =============================================================================


async def verify_fet_payment(
    *,
    transaction_id: str,
    wallet_address: str,
    payment_information: ActivePayment,
    context: PaymentContext,
) -> VerificationResult:
    """Verify that a FET transaction sent the expected amount to recipient.

    Main entry point for FET payment verification. Fetches transaction data
    from the FET LCD endpoint, verifies execution status, and validates
    that the payment details (recipient and amount) match expectations.

    Verification Steps:
        1. Fetch transaction data from LCD (with retries)
        2. Validate payment information contains expected amount
        3. Check transaction execution status (code == 0)
        4. Verify payment via messages or events

    Args:
        transaction_id: Transaction hash to verify.
        wallet_address: Expected recipient wallet address.
        payment_information: Active payment containing expected FET amount.
        context: PaymentContext for logging and identification.

    Returns:
        VerificationResult with 'verified' boolean and optional 'error' message.

    Examples:
        >>> result = await verify_fet_payment(
        ...     transaction_id="ABC123...",
        ...     wallet_address="fetch1abc...",
        ...     payment_information={"fet": Decimal("10.5"), ...},
        ...     context=payment_context,
        ... )
        >>> if result["verified"]:
        ...     print("Payment verified!")
    """
    # Fetch transaction data
    tx_data = await _fetch_transaction(
        tx_hash=transaction_id,
        context=context,
    )

    amount_fet = payment_information["fet"]

    if not amount_fet:
        context.logger.error(
            (
                "[PaymentUtils]: %s | %s | %s | "
                "Payment information missing expected amount. "
                "Payment info: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            payment_information,
        )
        return {
            "verified": False,
            "error": "Payment information missing expected amount",
        }

    if not tx_data:
        return {
            "verified": False,
            "error": "Transaction not found after retries",
        }

    # Check transaction status
    if not _check_transaction_status(tx_data=tx_data, context=context):
        return {
            "verified": False,
            "error": "Transaction failed",
        }

    # Verify payment details
    verified = _verify_transaction_details(
        tx_data=tx_data,
        recipient_address=wallet_address,
        expected_amount_fet=float(amount_fet),
        context=context,
    )

    result: VerificationResult = {
        "verified": verified,
        "error": None if verified else "No matching transfer found",
    }

    return result
