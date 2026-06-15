# Copyright (c) 2026 Tejus Gupta
"""Payment-related constants for runtime payment providers."""

from typing import Final, Literal

PAYMENT_TIMEOUT_SECONDS: Final[int] = 60 * 30

STRIPE_SUCCESS_URL: Final[str] = "https://agentverse.ai/payment-success"
STRIPE_UI_MODE: Final[Literal["custom", "embedded_page", "hosted"]] = "embedded_page"
STRIPE_REDIRECT_ON_COMPLETION: Final[Literal["always", "if_required", "never"]] = (
    "if_required"
)
STRIPE_PAYMENT_METHOD_TYPES: Final[list[Literal["card"]]] = ["card"]
STRIPE_MODE: Final[Literal["payment", "setup", "subscription"]] = "payment"
ZERO_DECIMAL_CURRENCIES = {
    "bif",
    "clp",
    "djf",
    "gnf",
    "jpy",
    "kmf",
    "krw",
    "mga",
    "pyg",
    "rwf",
    "ugx",
    "vnd",
    "vuv",
    "xaf",
    "xof",
    "xpf",
}

JWKS_ROUTE: Final[str] = "/.well-known/jwks.json"
SKYFILE_TOKEN_ROUTE: Final[str] = "/api/v1/tokens/charge"
JWT_ALGORITHM = "ES256"

DEVELOPMENT_DEFAULT_APP_BASE = "https://app-qa.skyfire.xyz"
DEVELOPMENT_DEFAULT_API_BASE = "https://api-qa.skyfire.xyz"
DEVELOPMENT_JWKS_URL = f"{DEVELOPMENT_DEFAULT_APP_BASE}{JWKS_ROUTE}"
DEVELOPMENT_SKYFIRE_TOKENS_API_URL = (
    f"{DEVELOPMENT_DEFAULT_API_BASE}{SKYFILE_TOKEN_ROUTE}"
)
DEVELOPMENT_JWT_ISSUER = DEVELOPMENT_DEFAULT_APP_BASE

PRODUCTION_DEFAULT_APP_BASE = "https://app.skyfire.xyz"
PRODUCTION_DEFAULT_API_BASE = "https://api.skyfire.xyz"
PRODUCTION_JWKS_URL = f"{PRODUCTION_DEFAULT_APP_BASE}{JWKS_ROUTE}"
PRODUCTION_SKYFIRE_TOKENS_API_URL = (
    f"{PRODUCTION_DEFAULT_API_BASE}{SKYFILE_TOKEN_ROUTE}"
)
PRODUCTION_JWT_ISSUER = PRODUCTION_DEFAULT_APP_BASE

FET_VERIFY_ATTEMPTS: Final[int] = 5
FET_VERIFY_DELAY_SEC: Final[float] = 2.0
FET_DENOM_SCALE: Final[float] = 1e18
HTTP_STATUS_OK: Final[int] = 200
