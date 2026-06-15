# Copyright (c) 2026 Tejus Gupta
"""Production-ready Stripe payment integration.

This module provides utilities for creating Stripe Checkout Sessions and
verifying payment status. It supports embedded checkout mode for seamless
payment experiences within the agent UI.

Key Functions:
    create_embedded_checkout_session: Create a Stripe Checkout Session.
    verify_stripe_payment: Verify payment status by session ID.

Internal Helpers:
    _to_stripe_amount: Convert amounts to Stripe's smallest unit format.

Currency Handling:
    - Zero-decimal currencies (JPY, KRW, etc.) are passed as-is
    - Standard currencies are multiplied by 100 (10.50 USD -> 1050 cents)

Examples:
    Creating a checkout session::

        from setup.payments.stripe import create_embedded_checkout_session

        config = create_embedded_checkout_session(
            user_id="user123",
            session_id="session456",
            description="API usage",
            amount=Decimal("10.00"),
            currency="USD",
            product_name="AI Agent Service",
            service="query",
            stripe_secret_key="sk_...",
            stripe_publishable_key="pk_...",
            payment_reference="pay_ref_123",
            payment_timeout=3600,
            agent_name="MyAgent",
        )

    Verifying payment::

        from setup.payments.stripe import verify_stripe_payment

        result = verify_stripe_payment(
            transaction_id="cs_...",
            stripe_secret_key="sk_...",
        )

        if result["verified"]:
            print("Payment succeeded!")
"""

import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import stripe

from runtime.payments.constants import (
    STRIPE_MODE,
    STRIPE_PAYMENT_METHOD_TYPES,
    STRIPE_REDIRECT_ON_COMPLETION,
    STRIPE_SUCCESS_URL,
    STRIPE_UI_MODE,
    ZERO_DECIMAL_CURRENCIES,
)
from runtime.payments.types import (
    AgentName,
    Amount,
    Currency,
    IdempotencyKey,
    PaymentContext,
    PaymentDescription,
    ProductName,
    Service,
    SessionID,
    TimeoutSeconds,
    UserID,
    VerificationResult,
)

__all__ = [
    "create_embedded_checkout_session",
    "verify_stripe_payment",
]


# =============================================================================
# Amount Conversion
# =============================================================================


def _to_stripe_amount(
    amount: Amount, currency: Currency, context: PaymentContext
) -> int:
    """Convert a human-readable amount into Stripe's smallest unit.

    Stripe requires amounts in the smallest currency unit (e.g., cents for USD,
    yen for JPY). This function handles the conversion based on currency type.

    Args:
        amount: The amount in human-readable form (e.g., 10.50 for $10.50).
        currency: The ISO 4217 currency code (e.g., 'USD', 'JPY').
        context: Payment context for logging.

    Returns:
        The amount converted to the smallest currency unit as an integer.

    Examples:
        >>> _to_stripe_amount(Decimal("10.50"), "USD", context)
        1050
        >>> _to_stripe_amount(Decimal("1000"), "JPY", context)
        1000
    """
    context.logger.info(
        "[StripePayment]: %s | %s | %s | Converting amount %s %s to Stripe format",
        context.user_id,
        context.session_id,
        context.message_id,
        amount,
        currency,
    )

    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        result = int(amount)
        context.logger.debug(
            "[StripePayment]: %s | %s | %s | Zero-decimal currency %s: %s -> %s",
            context.user_id,
            context.session_id,
            context.message_id,
            currency,
            amount,
            result,
        )
        return result

    result = int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    context.logger.debug(
        "[StripePayment]: %s | %s | %s | Standard currency %s: %s -> %s cents",
        context.user_id,
        context.session_id,
        context.message_id,
        currency,
        amount,
        result,
    )
    return result


# =============================================================================
# Checkout Session Creation
# =============================================================================


def create_embedded_checkout_session(  # noqa: PLR0913
    *,
    user_id: UserID,
    session_id: SessionID,
    description: PaymentDescription,
    amount: Amount,
    currency: Currency,
    product_name: ProductName,
    service: Service,
    stripe_secret_key: str,
    stripe_publishable_key: str,
    payment_reference: IdempotencyKey,
    payment_timeout: TimeoutSeconds,
    agent_name: AgentName,
    context: PaymentContext,
) -> dict[str, Any] | None:
    """Create an embedded Stripe Checkout Session.

    Creates a Stripe Checkout Session configured for embedded UI mode,
    allowing seamless payment integration within the agent interface.
    The session includes full metadata for tracking and idempotency support.

    Session Configuration:
        - UI Mode: Embedded (no redirect during payment)
        - Redirect on Completion: If required by payment method
        - Payment Methods: Configurable via STRIPE_PAYMENT_METHOD_TYPES
        - Expiration: Based on payment_timeout parameter

    Args:
        user_id: The ID of the user making the payment.
        session_id: The ID of the chat session associated with the payment.
        description: A description of the payment for display in Stripe Checkout.
        amount: The amount to be charged, in human-readable form (e.g., 10.00).
        currency: The ISO 4217 currency code (e.g., 'USD', 'EUR').
        product_name: The name of the product or service being purchased.
        service: The specific service or action the payment is for.
        stripe_secret_key: The secret key for Stripe API authentication.
        stripe_publishable_key: The publishable key for frontend integration.
        payment_reference: A unique reference for idempotency.
        payment_timeout: Number of seconds until the session expires.
        agent_name: The name of the agent requesting the payment.
        context: Payment context for logging.

    Returns:
        On success: Dictionary containing:
            - ui_mode: The Stripe UI mode
            - publishable_key: Key for frontend initialization
            - client_secret: Secret for completing the checkout
            - checkout_session_id: The Stripe session ID
            - amount_cents: Amount in smallest currency unit
            - currency: The currency code

        On error: Dictionary containing:
            - error: Error message
            - unit_amount: The attempted amount
            - currency: The currency code
    """
    context.logger.info(
        "[StripePayment]: %s | %s | %s | Creating Stripe checkout session for %s %s",
        context.user_id,
        context.session_id,
        context.message_id,
        amount,
        currency,
    )

    stripe.api_key = stripe_secret_key

    return_url = (
        f"{STRIPE_SUCCESS_URL}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={session_id}"
        f"&user={user_id}"
    )

    expires_at = int(time.time()) + payment_timeout
    unit_amount = _to_stripe_amount(amount, currency, context)

    context.logger.debug(
        "[StripePayment]: %s | %s | %s | Session config - unit_amount: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        unit_amount,
    )

    try:
        checkout_session = stripe.checkout.Session.create(
            ui_mode=STRIPE_UI_MODE,
            redirect_on_completion=STRIPE_REDIRECT_ON_COMPLETION,
            payment_method_types=STRIPE_PAYMENT_METHOD_TYPES,
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {
                            "name": product_name,
                            "description": description,
                        },
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }
            ],
            mode=STRIPE_MODE,
            return_url=return_url,
            expires_at=expires_at,
            payment_intent_data={
                "description": description,
                "metadata": {
                    "agent": agent_name,
                    "service": service,
                    "payment_reference": payment_reference,
                },
            },
            metadata={
                "sender": user_id,
                "session_id": session_id,
                "payment_reference": payment_reference,
                "agent": agent_name,
                "service": service,
            },
            idempotency_key=payment_reference,
        )
        context.logger.info(
            (
                "[StripePayment]: %s | %s | %s | Stripe checkout session created "
                "successfully - session_id: %s"
            ),
            context.user_id,
            context.session_id,
            context.message_id,
            checkout_session.id,
        )
    except stripe.StripeError as e:
        context.logger.exception(
            "[StripePayment]: %s | %s | %s | Error creating Stripe checkout session.",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return {"error": str(e), "unit_amount": unit_amount, "currency": currency}
    else:
        return {
            "ui_mode": STRIPE_UI_MODE,
            "publishable_key": stripe_publishable_key,
            "client_secret": checkout_session.client_secret,
            "checkout_session_id": checkout_session.id,
            "amount_cents": unit_amount,
            "currency": currency,
        }


# =============================================================================
# Payment Verification
# =============================================================================


def verify_stripe_payment(
    transaction_id: str,
    stripe_secret_key: str,
    context: PaymentContext,
    *,
    expected_amount: Amount | None = None,
    expected_currency: Currency | None = None,
) -> VerificationResult:
    """Verify if a Stripe Checkout Session has been paid.

    Retrieves the checkout session from Stripe and checks the payment_status
    field to determine if the payment was completed successfully.

    Args:
        transaction_id: The Stripe Checkout Session ID to verify.
        stripe_secret_key: The secret key for Stripe API authentication.
        context: Payment context for logging.
        expected_amount: Optional expected charge amount for post-pay validation.
        expected_currency: Optional expected ISO currency for post-pay validation.

    Returns:
        VerificationResult with:
            - verified: True if payment_status is 'paid'
            - error: None on success, error message on failure

    Examples:
        >>> result = verify_stripe_payment("cs_test_...", "sk_test_...", context)
        >>> if result["verified"]:
        ...     process_order()
    """
    stripe.api_key = stripe_secret_key
    try:
        session = stripe.checkout.Session.retrieve(transaction_id)
        paid = getattr(session, "payment_status", None) == "paid"
        context.logger.info(
            "[StripePayment]: %s | %s | %s | Payment verification result: %s",
            context.user_id,
            context.session_id,
            context.message_id,
            paid,
        )
        if not paid:
            return {"verified": False, "error": "Payment not completed"}

        if expected_amount is not None and expected_currency is not None:
            expected_cents = _to_stripe_amount(
                expected_amount,
                expected_currency,
                context,
            )
            session_amount = getattr(session, "amount_total", None)
            session_currency = getattr(session, "currency", None)
            if session_amount != expected_cents:
                return {
                    "verified": False,
                    "error": (
                        f"Stripe amount mismatch: expected {expected_cents}, "
                        f"got {session_amount}."
                    ),
                }
            if (
                session_currency is not None
                and str(session_currency).upper() != expected_currency.upper()
            ):
                return {
                    "verified": False,
                    "error": (
                        f"Stripe currency mismatch: expected {expected_currency}, "
                        f"got {session_currency}."
                    ),
                }

    except stripe.StripeError as e:
        context.logger.exception(
            "[StripePayment]: %s | %s | %s | Error verifying Stripe payment.",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return {"verified": False, "error": str(e)}
    else:
        return {"verified": True, "error": None}
