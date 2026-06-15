# src/create_agentverse_agent/context.py
"""Project configuration models for scaffold generation."""

from __future__ import annotations

import logging
import re
import secrets
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self, override

from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)

DEFAULT_AVATAR_URL = (
    "https://storage.googleapis.com/agentverse-prod-assets/"
    "agent-avatars-pub/1555524032.png"
)
DEFAULT_BANNER_URL = (
    "https://storage.googleapis.com/agentverse-prod-assets/"
    "agent-banners-pub/360350005.png"
)

_WINDOW_PATTERN = re.compile(r"^(?P<n>\d+)(?P<u>s|m|h)$", re.IGNORECASE)


class ContextError(Exception):
    """Raised when project configuration is invalid."""


def parse_window_seconds(window: str) -> int:
    """Parse rate-limit windows (``30s``, ``1m``, ``2h``) to seconds."""
    match = _WINDOW_PATTERN.match(window.strip())
    if match is None:
        msg = f"Invalid rate-limit window: {window!r} (expected e.g. 30s, 1m, 2h)"
        raise ContextError(msg)
    amount = int(match.group("n"))
    unit = match.group("u").lower()
    multiplier = {"s": 1, "m": 60, "h": 3600}[unit]
    return amount * multiplier


class GeoLocation(BaseModel):
    """Geolocation metadata for an agent."""

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    radius: float = 0


class AgentIdentity(BaseModel):
    """Agent identity and presentation settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    handle: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    port: int = Field(default=8000, ge=1024, le=65535)
    avatar_url: str | None = DEFAULT_AVATAR_URL
    banner_url: str | None = DEFAULT_BANNER_URL
    geo_location: GeoLocation | None = None


class RateLimitWindow(BaseModel):
    """Rate limit bucket definition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_requests: int = Field(ge=1)
    window: str

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        parse_window_seconds(self.window)
        return self


class RateLimitExemptions(BaseModel):
    """Rate limit exemption policy."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    policy: Literal["none", "all", "allow", "deny"]
    identifiers: list[str] | None = None


class RateLimits(BaseModel):
    """Session and user rate limits."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    session: RateLimitWindow
    user: RateLimitWindow
    exemptions: RateLimitExemptions


class AccessControl(BaseModel):
    """Protocol access control policy."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    policy: Literal["all", "none", "allow", "deny"]
    identifiers: list[str] | None = None


class PaymentMethodState(StrEnum):
    """Payment method availability."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class PaymentMethods(BaseModel):
    """Supported payment methods."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    fet: PaymentMethodState = PaymentMethodState.ENABLED
    skyfire: PaymentMethodState = PaymentMethodState.DISABLED
    stripe: PaymentMethodState = PaymentMethodState.DISABLED


class ProtocolConfig(BaseModel):
    """Shared protocol configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    maximum_processing_time_seconds: int = Field(ge=1)
    rate_limits: RateLimits
    access_control: AccessControl


class ChatProtocolConfig(ProtocolConfig):
    """Chat protocol configuration."""


class PaymentProtocolConfig(ProtocolConfig):
    """Payment protocol configuration."""

    methods: PaymentMethods


class ProtocolsConfig(BaseModel):
    """All protocol configurations."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    chat: ChatProtocolConfig
    payment: PaymentProtocolConfig


class CoordinatorConfig(BaseModel):
    """Postgres coordinator TTLs and heartbeat interval."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    heartbeat_interval_seconds: int = Field(default=20, ge=1)
    assignment_ttl_seconds: int = Field(default=90, ge=1)
    processing_ttl_seconds: int = Field(default=180, ge=1)
    session_lock_ttl_seconds: int = Field(default=180, ge=1)
    reclaim_worker_stale_seconds: int = Field(default=45, ge=1)


class RuntimeConfig(BaseModel):
    """Runtime behavior settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    max_concurrent_sessions: int = Field(default=5, ge=1)
    mailbox: bool = True
    handle_messages_concurrently: bool = True
    network: Literal["testnet", "mainnet"] = "testnet"
    coordinator: CoordinatorConfig = Field(default_factory=CoordinatorConfig)


class AgentYmlConfig(BaseModel):
    """Validated agent.yml document."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    agent: AgentIdentity
    protocols: ProtocolsConfig
    runtime: RuntimeConfig


class EnvSecrets(BaseModel):
    """Environment-backed secrets for generated .env."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    agentverse_api_key: str | None = Field(default=None, min_length=20, max_length=1000)
    agent_seed: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        min_length=1,
        max_length=500,
        pattern=r"^[a-zA-Z0-9]+$",
    )
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_database: str = "agent"
    postgres_user: str = "agent_pod"
    postgres_password: str = Field(
        default_factory=lambda: secrets.token_urlsafe(16),
        min_length=8,
        max_length=255,
    )
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    skyfire_api_key: str | None = None
    skyfire_seller_account_id: str | None = None
    skyfire_service_id: str | None = None
    fet_lcd_url: str | None = None
    agent_port: int = Field(default=8000, ge=1024, le=65535)


def _default_protocol_config() -> ProtocolConfig:
    return ProtocolConfig(
        maximum_processing_time_seconds=180,
        rate_limits=RateLimits(
            session=RateLimitWindow(max_requests=10, window="1m"),
            user=RateLimitWindow(max_requests=50, window="1m"),
            exemptions=RateLimitExemptions(policy="none", identifiers=None),
        ),
        access_control=AccessControl(policy="all", identifiers=None),
    )


def default_yml_config(
    *,
    name: str | None = None,
    handle: str | None = None,
    description: str | None = None,
    port: int = 8000,
    network: Literal["testnet", "mainnet"] = "testnet",
) -> AgentYmlConfig:
    """Build default agent.yml configuration for quick-start mode."""
    seed_fragment = secrets.token_hex(4)
    resolved_name = name or f"Agent {seed_fragment}"
    resolved_handle = handle or f"agent-{seed_fragment.lower()}"
    resolved_description = (
        description or "An ASI1 compatible agent built using 'create-agentverse-agent'."
    )
    chat = ChatProtocolConfig.model_validate(_default_protocol_config().model_dump())
    payment = PaymentProtocolConfig(
        **_default_protocol_config().model_dump(),
        methods=PaymentMethods(),
    )
    return AgentYmlConfig(
        agent=AgentIdentity(
            name=resolved_name,
            description=resolved_description,
            handle=resolved_handle,
            port=port,
        ),
        protocols=ProtocolsConfig(chat=chat, payment=payment),
        runtime=RuntimeConfig(network=network),
    )


class ProjectContext(BaseModel):
    """Single source of truth for scaffold generation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    author_name: str = "Tejus Gupta"
    author_email: str = "tejus3131@tejusgupta.dev"
    yml: AgentYmlConfig
    secrets: EnvSecrets

    @model_validator(mode="after")
    def sync_ports_and_validate_payments(self) -> Self:
        self.secrets.agent_port = self.yml.agent.port
        methods = self.yml.protocols.payment.methods
        if methods.stripe is PaymentMethodState.ENABLED and (
            not self.secrets.stripe_secret_key
            or not self.secrets.stripe_publishable_key
        ):
            raise ContextError(
                "STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY required when "
                "stripe is enabled"
            )
        if methods.skyfire is PaymentMethodState.ENABLED and (
            not self.secrets.skyfire_api_key
            or not self.secrets.skyfire_seller_account_id
            or not self.secrets.skyfire_service_id
        ):
            raise ContextError(
                "SKYFIRE_API_KEY, SKYFIRE_SELLER_ACCOUNT_ID, and "
                "SKYFIRE_SERVICE_ID required when skyfire is enabled"
            )
        return self

    @classmethod
    def create_default(cls) -> ProjectContext:
        """Create a quick-start project context with sensible defaults."""
        yml = default_yml_config()
        secrets = EnvSecrets(agent_port=yml.agent.port)
        return cls(
            project_name=yml.agent.handle,
            yml=yml,
            secrets=secrets,
        )

    @property
    def project_path(self) -> Path:
        return Path.cwd() / self.project_name

    @property
    def display_name(self) -> str:
        return self.yml.agent.name

    def is_agentverse_configured(self) -> bool:
        return bool(self.secrets.agentverse_api_key)

    def revalidated(self) -> ProjectContext:
        """Return a fresh validated copy after interactive mutations."""
        return ProjectContext.model_validate(
            {
                "project_name": self.project_name,
                "author_name": self.author_name,
                "author_email": self.author_email,
                "yml": self.yml.model_dump(),
                "secrets": self.secrets.model_dump(),
            }
        )

    @override
    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        data.update(
            {
                "display_name": self.display_name,
                "project_path": str(self.project_path),
                "agent": self.yml.agent.model_dump(),
                "protocols": self.yml.protocols.model_dump(),
                "runtime": self.yml.runtime.model_dump(),
            }
        )
        return data

    @override
    def __repr__(self) -> str:
        fields = ", ".join(
            f"{k}={v!r}"
            for k, v in self.model_dump().items()
            if k
            not in {
                "secrets",
                "agent_seed",
                "agentverse_api_key",
                "stripe_secret_key",
                "stripe_publishable_key",
                "skyfire_api_key",
                "postgres_password",
            }
        )
        return f"{self.__class__.__name__}({fields})"


# Backward-compatible alias for tests during migration
AgentContext = ProjectContext
AgentContextError = ContextError
