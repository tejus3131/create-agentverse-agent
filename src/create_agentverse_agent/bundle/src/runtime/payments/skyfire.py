# Copyright (c) 2026 Tejus Gupta
"""Production-ready Skyfire payment integration.

This module provides utilities for verifying and charging Skyfire payment tokens.
Skyfire uses JWT tokens for payment authorization which are verified against
JWKS (JSON Web Key Set) endpoints before charging.

Key Functions:
    verify_skyfire_payment: Main entry point for Skyfire payment verification.
    verify_token_claims: Verify JWT token claims against JWKS.
    charge_token: Execute the charge operation on a verified token.

Verification Flow:
    1. Extract key ID (kid) from JWT header
    2. Fetch JWKS from environment-appropriate endpoint
    3. Verify JWT signature and claims (audience, issuer, service)
    4. Charge the token via Skyfire API

Environment Support:
    Both production and development environments are supported with
    different JWKS URLs, JWT issuers, and API endpoints.

Examples:
    Verifying a Skyfire payment::

        from setup.payments.skyfire import verify_skyfire_payment

        result = await verify_skyfire_payment(
            skyfire_service_id="service123",
            skyfire_seller_account_id="seller456",
            skyfire_api_key="api_key_...",
            transaction_id="jwt_token_...",
            context=payment_context,
            payment_information=active_payment,
        )

        if result["verified"]:
            print("Payment charged successfully!")
"""

from logging import Logger

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWTError

from runtime.payments.constants import (
    DEVELOPMENT_JWKS_URL,
    DEVELOPMENT_JWT_ISSUER,
    DEVELOPMENT_SKYFIRE_TOKENS_API_URL,
    JWT_ALGORITHM,
    PRODUCTION_JWKS_URL,
    PRODUCTION_JWT_ISSUER,
    PRODUCTION_SKYFIRE_TOKENS_API_URL,
)
from runtime.payments.types import ActivePayment, PaymentContext, VerificationResult

__all__ = [
    "charge_token",
    "verify_skyfire_payment",
    "verify_token_claims",
]


# =============================================================================
# Token Verification
# =============================================================================


def verify_token_claims(
    skyfire_seller_account_id: str,
    skyfire_service_id: str,
    token: str,
    is_production: bool,
    logger: Logger,
) -> bool:
    """Verify the claims of a Skyfire JWT token.

    Validates the JWT token by:
        1. Extracting the key ID from the token header
        2. Fetching the JWKS from the appropriate endpoint
        3. Verifying the signature using the matching key
        4. Validating claims (audience, issuer, service ID)

    Args:
        skyfire_seller_account_id: Expected seller account ID (JWT audience).
        skyfire_service_id: Expected service ID (checked against 'ssi' claim).
        token: The JWT token to verify.
        is_production: Use production Skyfire endpoints when True.
        logger: Logger for verification steps and errors.

    Returns:
        True if token is valid and all claims are verified, False otherwise.
    """
    logger.info(
        "[SkyfirePayment] Verifying Skyfire token - production: %s, service_id: %s",
        is_production,
        skyfire_service_id,
    )

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            logger.warning("[SkyfirePayment] Token header missing 'kid' field")
            return False

        logger.debug("[SkyfirePayment] Token kid: %s", kid)

        if is_production:
            jwks_url = PRODUCTION_JWKS_URL
            jwt_issuer = PRODUCTION_JWT_ISSUER
        else:
            jwks_url = DEVELOPMENT_JWKS_URL
            jwt_issuer = DEVELOPMENT_JWT_ISSUER

        logger.debug("[SkyfirePayment] Fetching JWKS from: %s", jwks_url)

        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[JWT_ALGORITHM],
            audience=skyfire_seller_account_id,
            issuer=jwt_issuer,
            options={"verify_aud": True},
        )
        ssi = claims.get("ssi")

        logger.debug("[SkyfirePayment] Token claims verified - ssi: %s", ssi)

        if ssi != skyfire_service_id:
            logger.warning(
                "[SkyfirePayment] Service ID mismatch - expected: %s, got: %s",
                skyfire_service_id,
                ssi,
            )
            return False

        logger.info("[SkyfirePayment] Skyfire token verified OK")
    except (PyJWTError, InvalidTokenError):
        logger.exception("[SkyfirePayment] Skyfire token verification failed")
        return False
    except httpx.HTTPError:
        logger.exception("[SkyfirePayment] JWKS fetch error")
        return False
    except Exception:
        logger.exception("[SkyfirePayment] Unexpected verification error")
        return False
    else:
        return True


# =============================================================================
# Token Charging
# =============================================================================


async def charge_token(
    skyfire_api_key: str,
    is_production: bool,
    token: str,
    amount_usdc: str,
    logger: Logger,
    idempotency_key: str,
) -> bool:
    """Charge a verified Skyfire token.

    Executes the charge operation on a previously verified token. Uses
    idempotency key to prevent duplicate charges.

    Args:
        skyfire_api_key: API key for Skyfire authentication.
        is_production: Use production Skyfire endpoints when True.
        token: The verified JWT token to charge.
        amount_usdc: Amount to charge in USDC (e.g., '12.34').
        logger: Logger for operation logging.
        idempotency_key: Unique key to prevent duplicate charges.

    Returns:
        True if charge succeeded, False otherwise.
    """
    logger.info(
        "[SkyfirePayment] Charging Skyfire token - amount: %s USDC",
        amount_usdc,
    )

    payload = {"token": token, "chargeAmount": str(amount_usdc)}
    headers = {
        "skyfire-api-key": skyfire_api_key,
        "skyfire-api-version": "2",
        "content-type": "application/json",
    }
    headers["x-idempotency-key"] = idempotency_key

    if is_production:
        tokens_api_url = PRODUCTION_SKYFIRE_TOKENS_API_URL
    else:
        tokens_api_url = DEVELOPMENT_SKYFIRE_TOKENS_API_URL

    logger.debug("[SkyfirePayment] Charge request to: %s", tokens_api_url)

    try:
        async with httpx.AsyncClient() as session:
            resp = await session.post(
                tokens_api_url, json=payload, headers=headers, timeout=30.0
            )
            resp.raise_for_status()
            logger.info(
                "[SkyfirePayment] Charge successful - status: %s", resp.status_code
            )
            return True

    except httpx.HTTPStatusError as e:
        logger.exception(
            "[SkyfirePayment] Skyfire charge failed - status: %s, body: %s",
            e.response.status_code,
            e.response.text,
        )
        return False
    except httpx.HTTPError:
        logger.exception("[SkyfirePayment] Skyfire charge network error")
        return False
    except Exception:
        logger.exception("[SkyfirePayment] Skyfire charge unexpected error")
        return False


# =============================================================================
# Public API
# =============================================================================


async def verify_skyfire_payment(
    skyfire_service_id: str,
    skyfire_seller_account_id: str,
    skyfire_api_key: str,
    transaction_id: str,
    context: PaymentContext,
    payment_information: ActivePayment,
) -> VerificationResult:
    """Verify and charge a Skyfire payment.

    Main entry point for Skyfire payment verification. Performs full
    verification of the JWT token and executes the charge if valid.

    Verification Steps:
        1. Extract USDC amount from payment information
        2. Verify JWT token claims (signature, audience, issuer, service)
        3. Charge the verified token

    Args:
        skyfire_service_id: Expected service ID for verification.
        skyfire_seller_account_id: Expected seller account ID (JWT audience).
        skyfire_api_key: API key for charging the token.
        transaction_id: The JWT token to verify and charge.
        context: Payment context with logger and environment info.
        payment_information: Active payment containing USDC amount and idempotency key.

    Returns:
        VerificationResult with 'verified' boolean and optional 'error' message.

    Examples:
        >>> result = await verify_skyfire_payment(
        ...     skyfire_service_id="svc_123",
        ...     skyfire_seller_account_id="acct_456",
        ...     skyfire_api_key="sk_...",
        ...     transaction_id="eyJ...",
        ...     context=payment_context,
        ...     payment_information={"usdc": Decimal("10.00"), ...},
        ... )
    """
    context.logger.info(
        "[SkyfirePayment]: %s | %s | %s | Verifying Skyfire payment",
        context.user_id,
        context.session_id,
        context.message_id,
    )
    usdc = payment_information["usdc"]
    if not usdc:
        context.logger.error(
            "[SkyfirePayment]: %s | %s | %s | Payment information missing USDC amount",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return {"verified": False, "error": "Payment information missing USDC amount"}

    context.logger.debug(
        "[SkyfirePayment]: %s | %s | %s | Expected USDC amount: %s",
        context.user_id,
        context.session_id,
        context.message_id,
        usdc,
    )

    if not verify_token_claims(
        skyfire_seller_account_id=skyfire_seller_account_id,
        skyfire_service_id=skyfire_service_id,
        token=transaction_id,
        is_production=context.is_production,
        logger=context.logger,
    ):
        context.logger.warning(
            "[SkyfirePayment]: %s | %s | %s | Token verification failed",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return {"verified": False, "error": "Token verification failed"}

    if not await charge_token(
        skyfire_api_key=skyfire_api_key,
        is_production=context.is_production,
        token=transaction_id,
        amount_usdc=str(usdc),
        logger=context.logger,
        idempotency_key=payment_information["idempotency_key"],
    ):
        context.logger.warning(
            "[SkyfirePayment]: %s | %s | %s | Token charge failed",
            context.user_id,
            context.session_id,
            context.message_id,
        )
        return {"verified": False, "error": "Token charge failed"}

    context.logger.info(
        "[SkyfirePayment]: %s | %s | %s | Skyfire payment verified successfully",
        context.user_id,
        context.session_id,
        context.message_id,
    )
    return {"verified": True, "error": None}
