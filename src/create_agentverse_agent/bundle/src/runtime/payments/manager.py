# Copyright (c) 2026 Tejus Gupta
"""Payment management module for orchestrating payment requests and verification.

This module provides the central payment management functionality, handling:
    - Currency conversion (fiat to USDC)
    - Cryptocurrency conversion (USDC to FET)
    - Payment request creation with multiple payment methods
    - Payment verification routing to appropriate providers

Key Functions:
    create_payment_request: Create RequestPayment and ActivePayment objects.
    verify_payment: Route payment verification to appropriate provider.

Currency Conversion:
    - Fiat to USDC: Uses Frankfurter API (no API key required)
    - USDC to FET: Uses Binance API (no API key required)

Supported Payment Methods:
    - Skyfire: USDC payments via JWT tokens
    - FET: Direct FET blockchain transfers
    - Stripe: Credit/debit card payments

Examples:
    Creating a payment request::

        from setup.payments.manager import create_payment_request

        payment_data = PaymentData(
            amount=Decimal("10.00"),
            currency="USD",
            description="API usage fee",
            ...
        )

        request, active = create_payment_request(
            data=payment_data,
            context=payment_context,
            methods=payment_methods,
        )

    Verifying a payment::

        from setup.payments.manager import verify_payment

        result = await verify_payment(
            transaction_id="tx_123...",
            funds=funds_object,
            context=payment_context,
            methods=payment_methods,
            payment_information=active_payment,
        )
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from logging import Logger
from typing import Any

import httpx
from uagents_core.contrib.protocols.payment import Funds, RequestPayment

from runtime.payments.config import Methods, PaymentMethodName
from runtime.payments.constants import PAYMENT_TIMEOUT_SECONDS
from runtime.payments.exceptions import PaymentConversionError
from runtime.payments.fet import verify_fet_payment
from runtime.payments.logging_utils import sanitize_request_payment_for_log
from runtime.payments.skyfire import verify_skyfire_payment
from runtime.payments.stripe import (
    create_embedded_checkout_session,
    verify_stripe_payment,
)
from runtime.payments.types import (
    FET,
    USDC,
    AcceptedFund,
    ActivePayment,
    Amount,
    Currency,
    PaymentContext,
    PaymentData,
    TransactionID,
    VerificationResult,
)

__all__ = [
    "create_payment_request",
    "verify_payment",
]


# =============================================================================
# Currency Conversion - Fiat to USDC
# =============================================================================


def _fx_to_usdc(amount: Amount, currency: Currency, logger: Logger) -> USDC:
    """Convert fiat/USD amount to USDC using Frankfurter API.

    Uses the free Frankfurter API (no API key required) to fetch live
    exchange rates for fiat currency conversion.

    Args:
        amount: The amount to convert.
        currency: ISO 4217 currency code (e.g., 'EUR', 'GBP', 'USD').
        logger: Logger instance for conversion logging.

    Returns:
        USDC equivalent rounded to 2 decimal places.

    Raises:
        PaymentConversionError: If conversion fails due to:
            - Missing currency code
            - Invalid or missing exchange rate
            - API timeout or network error
            - Invalid amount format
    """
    logger.info("[PaymentManager] Converting %s %s to USDC", amount, currency)

    cur = (currency or "").strip().upper()
    if not cur:
        logger.error("[PaymentManager] Currency code is required for conversion")
        msg = "Currency code is required for conversion."
        raise PaymentConversionError(msg)

    if cur in {"USD", "USDC"}:
        result = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        logger.debug("[PaymentManager] Direct USD/USDC: %s -> %s", amount, result)
        return result

    logger.debug("[PaymentManager] Fetching exchange rate for %s to USD", cur)

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(
                "https://api.frankfurter.dev/v1/latest",
                params={"from": cur, "to": "USD"},
            )
            r.raise_for_status()

        data = r.json()
        rates: dict[str, Any] = data.get("rates", {})
        usd_per_cur = Decimal(str(rates.get("USD", "0")))

        logger.debug("[PaymentManager] Exchange rate for %s: %s USD", cur, usd_per_cur)

        if usd_per_cur <= 0:
            logger.error(
                "[PaymentManager] Invalid or missing USD rate for currency=%s", cur
            )
            msg = f"Invalid or missing USD rate for currency: {cur}"
            raise PaymentConversionError(msg)

        result = (amount * usd_per_cur).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except InvalidOperation as e:
        logger.exception("[PaymentManager] Invalid amount or rate for conversion")
        msg = "Invalid amount or rate for conversion"
        raise PaymentConversionError(msg) from e
    except httpx.TimeoutException as e:
        logger.exception(
            "[PaymentManager] Frankfurter API request timed out for currency=%s", cur
        )
        msg = f"Frankfurter API request timed out for currency={cur}"
        raise PaymentConversionError(msg) from e
    except httpx.RequestError as e:
        logger.exception("[PaymentManager] Frankfurter API request failed")
        msg = f"Frankfurter API request failed: {e}"
        raise PaymentConversionError(msg) from e
    except httpx.HTTPStatusError as e:
        logger.exception(
            "[PaymentManager] Frankfurter API returned error status %s",
            e.response.status_code,
        )
        msg = (
            f"Frankfurter API error: status={e.response.status_code} "
            f"body={e.response.text}"
        )
        raise PaymentConversionError(msg) from e
    except (KeyError, TypeError, ValueError) as e:
        logger.exception("[PaymentManager] Failed to parse Frankfurter API response")
        msg = f"Failed to parse Frankfurter API response: {e}"
        raise PaymentConversionError(msg) from e
    else:
        logger.info(
            "[PaymentManager] FX conversion: %s %s -> %s USDC", amount, cur, result
        )
        return result


# =============================================================================
# Cryptocurrency Conversion - USDC to FET
# =============================================================================


def _fet_usdc_price(logger: Logger) -> Decimal:
    """Fetch live FET/USDC price from Binance public API.

    Uses the free Binance API (no API key required) to fetch the
    current FET/USDC trading pair price.

    Args:
        logger: Logger instance for price fetch logging.

    Returns:
        Current FET/USDC price as Decimal.

    Raises:
        PaymentConversionError: If price fetch fails due to:
            - Invalid or zero price received
            - API timeout or network error
            - Response parsing failure
    """
    logger.debug("[PaymentManager] Fetching FET/USDC price from Binance")

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "FETUSDC"},
            )
            r.raise_for_status()

        data = r.json()
        price = Decimal(str(data.get("price", "0")))

        if price <= 0:
            logger.error(
                "[PaymentManager] Invalid FET/USDC price received from Binance: %r",
                price,
            )
            msg = f"Invalid FET/USDC price received from Binance: {price}"
            raise PaymentConversionError(msg)

    except httpx.TimeoutException as e:
        logger.exception("[PaymentManager] Binance API request timed out")
        msg = "Binance API request timed out."
        raise PaymentConversionError(msg) from e
    except httpx.RequestError as e:
        logger.exception("[PaymentManager] Binance API request failed")
        msg = f"Binance API request failed: {e}"
        raise PaymentConversionError(msg) from e
    except httpx.HTTPStatusError as e:
        logger.exception(
            "[PaymentManager] Binance API returned error status %s",
            e.response.status_code,
        )
        msg = (
            f"Binance API error: status={e.response.status_code} body={e.response.text}"
        )
        raise PaymentConversionError(msg) from e
    except (KeyError, TypeError, ValueError) as e:
        logger.exception("[PaymentManager] Failed to parse Binance API response")
        msg = f"Failed to parse Binance API response: {e}"
        raise PaymentConversionError(msg) from e
    else:
        logger.info("[PaymentManager] Fetched FET/USDC price: %s", price)
        return price


def _usdc_to_fet(amount_usdc: USDC, logger: Logger) -> FET:
    """Convert USDC amount to FET using live Binance price.

    Fetches the current FET/USDC price and calculates the equivalent
    FET amount for the given USDC value.

    Args:
        amount_usdc: The USDC amount to convert.
        logger: Logger instance for conversion logging.

    Returns:
        FET equivalent rounded to 4 decimal places.

    Raises:
        PaymentConversionError: If conversion fails due to price fetch
            errors or calculation failures.
    """
    logger.info("[PaymentManager] Converting %s USDC to FET", amount_usdc)

    try:
        price = _fet_usdc_price(logger)
        amount_fet = (amount_usdc / price).quantize(Decimal("0.0001"))
    except PaymentConversionError as e:
        logger.exception(
            "[PaymentManager] Failed to convert USDC to FET: %s", e.message
        )
        msg = f"Failed to convert USDC to FET: {e.message}"
        raise PaymentConversionError(msg) from e
    else:
        logger.info(
            "[PaymentManager] Converted %s USDC to %s FET at price %s",
            amount_usdc,
            amount_fet,
            price,
        )
        return amount_fet


# =============================================================================
# Payment Request Creation
# =============================================================================


def create_payment_request(
    data: PaymentData,
    context: PaymentContext,
    methods: Methods,
) -> tuple[RequestPayment, ActivePayment]:
    """Create RequestPayment and ActivePayment objects for a payment.

    Builds payment request objects based on configured payment methods.
    Performs necessary currency conversions and creates Stripe checkout
    sessions as needed.

    Payment Method Processing:
        1. Skyfire: Convert to USDC, add to accepted funds
        2. FET: Convert to FET via USDC, add to accepted funds
        3. Stripe: Create embedded checkout session, add to accepted funds

    Args:
        data: PaymentData containing payment details (amount, currency, etc.).
        context: PaymentContext with logging and identification info.
        methods: Methods configuration with allowed methods and secrets.

    Returns:
        Tuple of (RequestPayment, ActivePayment) for protocol handling.

    Note:
        Currency conversions are performed lazily - USDC conversion only
        happens once even if multiple methods require it.
    """
    context.logger.info(
        "[PaymentManager]: %s | %s | %s | Creating payment request for %s %s - %s",
        context.user_id,
        context.session_id,
        context.message_id,
        data["amount"],
        data["currency"],
        data["description"],
    )

    context.logger.debug(
        "[PaymentManager]: %s | %s | %s | Allowed payment methods: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        [m.value for m in methods.allowed],
    )
    metadata: dict[str, Any] = {
        "description": data["description"],
        "product_name": data["product_name"],
        "service": data["service"],
        "agent_name": data["agent_name"],
    }
    accepted_funds: list[Funds] = []

    if PaymentMethodName.SKYFIRE in methods.allowed and methods.skyfire_secrets:
        context.logger.info(
            "[PaymentManager]: %s | %s | %s | Processing Skyfire payment method",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        metadata["skyfire_service_id"] = methods.skyfire_secrets.service_id
        amount_usdc = _fx_to_usdc(data["amount"], data["currency"], context.logger)
        accepted_funds.append(
            Funds(
                amount=f"{amount_usdc:.2f}",
                currency="USDC",
                payment_method="skyfire",
            )
        )
        context.logger.debug(
            "[PaymentManager]: %s | %s | %s | Skyfire: %s USDC",
            context.user_id,
            context.session_id,
            context.message_id,
            amount_usdc,
        )
    else:
        amount_usdc = None

    if PaymentMethodName.FET in methods.allowed:
        context.logger.info(
            "[PaymentManager]: %s | %s | %s | Processing FET payment method",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        metadata["provider_agent_wallet"] = context.wallet_address
        if not amount_usdc:
            amount_usdc = _fx_to_usdc(data["amount"], data["currency"], context.logger)
        amount_fet = _usdc_to_fet(amount_usdc, context.logger)
        accepted_funds.append(
            Funds(
                amount=f"{amount_fet:.5f}",
                currency="FET",
                payment_method="fet_direct",
            )
        )
        context.logger.debug(
            "[PaymentManager]: %s | %s | %s | FET: %s FET",
            context.user_id,
            context.session_id,
            context.message_id,
            amount_fet,
        )
    else:
        amount_fet = None

    if PaymentMethodName.STRIPE in methods.allowed and methods.stripe_secrets:
        context.logger.info(
            "[PaymentManager]: %s | %s | %s | Processing Stripe payment method",
            context.user_id,
            context.session_id,
            context.message_id,
        )

        stripe_config = create_embedded_checkout_session(
            user_id=context.user_id,
            session_id=context.session_id,
            description=data["description"],
            amount=data["amount"],
            currency=data["currency"],
            product_name=data["product_name"],
            service=data["service"],
            stripe_secret_key=methods.stripe_secrets.secret_key,
            stripe_publishable_key=methods.stripe_secrets.publishable_key,
            payment_reference=data["idempotency_key"],
            payment_timeout=PAYMENT_TIMEOUT_SECONDS,
            agent_name=data["agent_name"],
            context=context,
        )
        metadata["stripe"] = stripe_config
        accepted_funds.append(
            Funds(
                amount=f"{float(data['amount']):.2f}",
                currency=data["currency"],
                payment_method="stripe",
            )
        )

    request_payment = RequestPayment(
        accepted_funds=accepted_funds,
        recipient=context.agent_address,
        deadline_seconds=PAYMENT_TIMEOUT_SECONDS,
        description=data["description"],
        metadata=metadata,
        reference=data["idempotency_key"],
    )

    active_payment = ActivePayment(
        usdc=amount_usdc,
        fet=amount_fet,
        idempotency_key=data["idempotency_key"],
        message_id=context.message_id,
        amount=data["amount"],
        currency=data["currency"],
        accepted_funds=[
            AcceptedFund(
                amount=funds.amount,
                currency=funds.currency,
                payment_method=funds.payment_method,
            )
            for funds in accepted_funds
        ],
    )

    context.logger.info(
        "[PaymentManager]: %s | %s | %s | Payment request created.",
        context.user_id,
        context.session_id,
        context.message_id,
    )
    context.logger.debug(
        "[PaymentManager]: %s | %s | %s | RequestPayment: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        sanitize_request_payment_for_log(request_payment),
    )

    return request_payment, active_payment


# =============================================================================
# Payment Verification
# =============================================================================


async def verify_payment(  # noqa: PLR0911
    transaction_id: TransactionID,
    funds: Funds,
    context: PaymentContext,
    methods: Methods,
    payment_information: ActivePayment,
) -> VerificationResult:
    """Verify a payment by routing to the appropriate provider.

    Routes payment verification to the correct provider based on the
    payment_method field in the Funds object. Validates that required
    secrets are configured before attempting verification.

    Supported Payment Methods:
        - 'skyfire': Routes to verify_skyfire_payment
        - 'direct_fet': Routes to verify_fet_payment
        - 'stripe': Routes to verify_stripe_payment

    Args:
        transaction_id: The transaction ID or token to verify.
        funds: Funds object containing payment method and details.
        context: PaymentContext with logging and identification info.
        methods: Methods configuration with secrets for each provider.
        payment_information: ActivePayment with amounts and idempotency key.

    Returns:
        VerificationResult with 'verified' boolean and optional 'error' message.

    Note:
        Returns an error result (not raises) if the payment method is
        unsupported or secrets are not configured.
    """
    context.logger.info(
        "[PaymentManager]: %s | %s | %s | Verifying payment - transaction: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        transaction_id,
    )

    if funds.payment_method == "skyfire":
        if not methods.skyfire_secrets:
            context.logger.error(
                "[PaymentManager]: %s | %s | %s | Skyfire secrets not configured",
                context.user_id,
                context.session_id,
                context.message_id,
            )
            return {"verified": False, "error": "Skyfire secrets not configured"}

        context.logger.debug(
            "[PaymentManager]: %s | %s | %s | Routing to Skyfire verification",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return await verify_skyfire_payment(
            skyfire_service_id=methods.skyfire_secrets.service_id,
            skyfire_seller_account_id=methods.skyfire_secrets.seller_account_id,
            skyfire_api_key=methods.skyfire_secrets.api_key,
            transaction_id=transaction_id,
            context=context,
            payment_information=payment_information,
        )

    if funds.payment_method == "fet_direct":
        if PaymentMethodName.FET not in methods.allowed:
            context.logger.error(
                "[PaymentManager]: %s | %s | %s | FET payment method not enabled",
                context.user_id,
                context.session_id,
                context.message_id,
            )
            return {"verified": False, "error": "FET payment method not enabled"}

        context.logger.debug(
            "[PaymentManager]: %s | %s | %s | Routing to FET verification",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return await verify_fet_payment(
            transaction_id=transaction_id,
            wallet_address=context.wallet_address,
            payment_information=payment_information,
            context=context,
        )

    if funds.payment_method == "stripe":
        if not methods.stripe_secrets:
            context.logger.error(
                "[PaymentManager]: %s | %s | %s | Stripe secrets not configured",
                context.user_id,
                context.session_id,
                context.message_id,
            )
            return {"verified": False, "error": "Stripe secrets not configured"}

        context.logger.debug(
            "[PaymentManager]: %s | %s | %s | Routing to Stripe verification",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return verify_stripe_payment(
            transaction_id=transaction_id,
            stripe_secret_key=methods.stripe_secrets.secret_key,
            context=context,
            expected_amount=payment_information.get("amount"),
            expected_currency=payment_information.get("currency"),
        )

    context.logger.error(
        "[PaymentManager]: %s | %s | %s | Unsupported payment method: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        funds.payment_method,
    )
    return {
        "verified": False,
        "error": f"Unsupported payment method: {funds.payment_method}",
    }
