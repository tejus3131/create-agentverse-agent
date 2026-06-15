# Copyright (c) 2026 Tejus Gupta
"""Build enabled payment methods + secrets from agent.yml and env."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shared.settings import PaymentMethodState, Secrets, Settings, SettingsError


class PaymentMethodName(StrEnum):
    """Runtime payment method identifiers."""

    STRIPE = "stripe"
    SKYFIRE = "skyfire"
    FET = "fet"


@dataclass(frozen=True, slots=True)
class StripeSecrets:
    """Stripe API credentials."""

    secret_key: str
    publishable_key: str


@dataclass(frozen=True, slots=True)
class SkyfireSecrets:
    """Skyfire API credentials and service identity."""

    api_key: str
    seller_account_id: str
    service_id: str


@dataclass(frozen=True, slots=True)
class Methods:
    """Enabled payment methods and provider credentials."""

    allowed: frozenset[PaymentMethodName]
    stripe_secrets: StripeSecrets | None = None
    skyfire_secrets: SkyfireSecrets | None = None


def methods_from_settings(settings: Settings) -> Methods:
    """Resolve payment methods from ``agent.yml`` + environment secrets.

    Args:
        settings: Loaded application settings.

    Returns:
        Methods for payment manager.

    Raises:
        SettingsError: If enabled method secrets are missing.
    """
    methods_cfg = settings.protocols.payment.methods
    allowed: set[PaymentMethodName] = set()
    if methods_cfg.stripe is PaymentMethodState.ENABLED:
        allowed.add(PaymentMethodName.STRIPE)
    if methods_cfg.skyfire is PaymentMethodState.ENABLED:
        allowed.add(PaymentMethodName.SKYFIRE)
    if methods_cfg.fet is PaymentMethodState.ENABLED:
        allowed.add(PaymentMethodName.FET)

    secrets = settings.secrets
    stripe = _stripe_secrets(secrets) if PaymentMethodName.STRIPE in allowed else None
    skyfire = (
        _skyfire_secrets(secrets) if PaymentMethodName.SKYFIRE in allowed else None
    )

    return Methods(
        allowed=frozenset(allowed),
        stripe_secrets=stripe,
        skyfire_secrets=skyfire,
    )


def validate_payment_config(settings: Settings) -> Methods:
    """Validate enabled payment methods and secrets at startup.

    Returns:
        Resolved payment methods for the running agent.

    Raises:
        SettingsError: Required provider secrets missing for an enabled method.
    """
    try:
        return methods_from_settings(settings)
    except SettingsError as exc:
        msg = f"Payment configuration invalid: {exc}"
        raise SettingsError(msg) from exc


def _stripe_secrets(secrets: Secrets) -> StripeSecrets:
    if not secrets.STRIPE_SECRET_KEY or not secrets.STRIPE_PUBLISHABLE_KEY:
        msg = (
            "STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY required when stripe enabled"
        )
        raise SettingsError(msg)
    return StripeSecrets(
        secret_key=secrets.STRIPE_SECRET_KEY,
        publishable_key=secrets.STRIPE_PUBLISHABLE_KEY,
    )


def _skyfire_secrets(secrets: Secrets) -> SkyfireSecrets:
    if not secrets.SKYFIRE_API_KEY or not secrets.SKYFIRE_SELLER_ACCOUNT_ID:
        msg = (
            "SKYFIRE_API_KEY and SKYFIRE_SELLER_ACCOUNT_ID required "
            "when skyfire enabled"
        )
        raise SettingsError(msg)
    if not secrets.SKYFIRE_SERVICE_ID:
        msg = "SKYFIRE_SERVICE_ID required when skyfire enabled"
        raise SettingsError(msg)
    return SkyfireSecrets(
        api_key=secrets.SKYFIRE_API_KEY,
        seller_account_id=secrets.SKYFIRE_SELLER_ACCOUNT_ID,
        service_id=secrets.SKYFIRE_SERVICE_ID,
    )
