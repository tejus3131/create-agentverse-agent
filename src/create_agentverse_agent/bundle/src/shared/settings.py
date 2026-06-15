# Copyright (c) 2026 Tejus Gupta
"""Load agent.yml config and environment secrets via a cached Settings singleton."""

from __future__ import annotations

import os
import re
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Final, Literal, Self, TypeVar, cast, overload

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_YML = PROJECT_ROOT / "agent.yml"

T = TypeVar("T")


class SettingsError(Exception):
    """Raised when settings or secrets cannot be loaded."""


class _Unset:
    """Sentinel for required environment variables."""


_UNSET = _Unset()


def _ensure_dotenv() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def _cast_env_value[T](raw: str, type_: type[T]) -> T:
    if type_ is str:
        return cast("T", raw)
    if type_ is int:
        return cast("T", int(raw))
    if type_ is float:
        return cast("T", float(raw))
    if type_ is bool:
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            parsed: bool = True
            return cast("T", parsed)
        if normalized in {"0", "false", "no", "off"}:
            parsed = False
            return cast("T", parsed)
        msg = f"Cannot parse {raw!r} as bool"
        raise SettingsError(msg)
    return type_(raw)  # type: ignore[call-arg]


@overload
def load[T](name: str, type_: type[T]) -> T: ...


@overload
def load[T](name: str, type_: type[T], default: T) -> T: ...


def load[T](name: str, type_: type[T], default: T | _Unset = _UNSET) -> T:
    """Read an environment variable, cast it, or return/default/raise.

    Args:
        name: The name of the environment variable.
        type_: The type to cast the environment variable to.
        default: The default value to return if the environment variable is not set.

    Returns:
        The environment variable, cast to the specified type.

    Raises:
        SettingsError: If the environment variable is not set
                        and no default is provided.
    """
    _ensure_dotenv()
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if default is not _UNSET:
            return cast("T", default)
        msg = f"Required environment variable {name!r} is not set"
        raise SettingsError(msg)
    return _cast_env_value(raw, type_)


_WINDOW_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<n>\d+)(?P<u>s|m|h)$",
    re.IGNORECASE,
)


def parse_window_seconds(window: str) -> int:
    """Parse human rate-limit windows (``30s``, ``1m``, ``2h``) to seconds.

    Returns:
        Window length in seconds.

    Raises:
        SettingsError: Window string is not in ``<n><s|m|h>`` form.
    """
    match = _WINDOW_PATTERN.match(window.strip())
    if match is None:
        msg = f"Invalid rate-limit window: {window!r} (expected e.g. 30s, 1m, 2h)"
        raise SettingsError(msg)
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


class AgentConfig(BaseModel):
    """Agent identity and presentation settings from agent.yml."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    handle: str
    port: int = Field(ge=1, le=65535)
    avatar_url: str | None = None
    banner_url: str | None = None
    geo_location: GeoLocation | None = None


class RateLimitWindow(BaseModel):
    """Rate limit bucket definition."""

    model_config = ConfigDict(extra="forbid")

    max_requests: int = Field(ge=1)
    window: str


class RateLimitExemptions(BaseModel):
    """Rate limit exemption policy."""

    model_config = ConfigDict(extra="forbid")

    policy: Literal["none", "all", "allow", "deny"]
    identifiers: list[str] | None = None


class RateLimits(BaseModel):
    """Session and user rate limits."""

    model_config = ConfigDict(extra="forbid")

    session: RateLimitWindow
    user: RateLimitWindow
    exemptions: RateLimitExemptions


class AccessControl(BaseModel):
    """Protocol access control policy."""

    model_config = ConfigDict(extra="forbid")

    policy: Literal["all", "none", "allow", "deny"]
    identifiers: list[str] | None = None


class PaymentMethodState(StrEnum):
    """Payment method availability."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class PaymentMethods(BaseModel):
    """Supported payment methods."""

    model_config = ConfigDict(extra="forbid")

    fet: PaymentMethodState = PaymentMethodState.ENABLED
    skyfire: PaymentMethodState = PaymentMethodState.ENABLED
    stripe: PaymentMethodState = PaymentMethodState.ENABLED


class ProtocolConfig(BaseModel):
    """Shared protocol configuration."""

    model_config = ConfigDict(extra="forbid")

    maximum_processing_time_seconds: int = Field(ge=1)
    rate_limits: RateLimits
    access_control: AccessControl


class ChatProtocolConfig(ProtocolConfig):
    """Chat protocol configuration."""


class PaymentProtocolConfig(ChatProtocolConfig):
    """Payment protocol configuration."""

    methods: PaymentMethods


class ProtocolsConfig(BaseModel):
    """All protocol configurations."""

    model_config = ConfigDict(extra="forbid")

    chat: ChatProtocolConfig
    payment: PaymentProtocolConfig


class CoordinatorConfig(BaseModel):
    """Postgres coordinator TTLs and heartbeat interval."""

    model_config = ConfigDict(extra="forbid")

    heartbeat_interval_seconds: int = Field(default=20, ge=1)
    assignment_ttl_seconds: int = Field(default=90, ge=1)
    processing_ttl_seconds: int = Field(default=180, ge=1)
    session_lock_ttl_seconds: int = Field(default=180, ge=1)
    reclaim_worker_stale_seconds: int = Field(default=45, ge=1)


class RuntimeConfig(BaseModel):
    """Runtime behavior settings."""

    model_config = ConfigDict(extra="forbid")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    max_concurrent_sessions: int = Field(ge=1)
    mailbox: bool = True
    handle_messages_concurrently: bool = True
    network: Literal["testnet", "mainnet"] = "testnet"
    coordinator: CoordinatorConfig = Field(default_factory=CoordinatorConfig)


class AgentYmlConfig(BaseModel):
    """Validated agent.yml document."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentConfig
    protocols: ProtocolsConfig
    runtime: RuntimeConfig


class Secrets:
    """Environment-backed secrets. Add fields with load(name, type, default)."""

    AGENTVERSE_API_KEY: str | None = load("AGENTVERSE_API_KEY", str, None)
    AGENT_SEED: str | None = load("AGENT_SEED", str, None)
    STRIPE_SECRET_KEY: str | None = load("STRIPE_SECRET_KEY", str, None)
    STRIPE_PUBLISHABLE_KEY: str | None = load("STRIPE_PUBLISHABLE_KEY", str, None)
    SKYFIRE_API_KEY: str | None = load("SKYFIRE_API_KEY", str, None)
    SKYFIRE_SELLER_ACCOUNT_ID: str | None = load("SKYFIRE_SELLER_ACCOUNT_ID", str, None)
    SKYFIRE_SERVICE_ID: str | None = load("SKYFIRE_SERVICE_ID", str, None)
    FET_LCD_URL: str | None = load("FET_LCD_URL", str, None)

    POSTGRES_HOST: str = load("POSTGRES_HOST", str)
    POSTGRES_PORT: int = load("POSTGRES_PORT", int)
    POSTGRES_DATABASE: str = load("POSTGRES_DATABASE", str)
    POSTGRES_USER: str = load("POSTGRES_USER", str)
    POSTGRES_PASSWORD: str = load("POSTGRES_PASSWORD", str)


class Settings:
    """Combined agent.yml config and environment secrets."""

    _instance: ClassVar[Settings | None] = None

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        """Create a new Settings instance.

        Args:
            args: The arguments to pass to the constructor.
            kwargs: The keyword arguments to pass to the constructor.

        Returns:
            The Settings instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cast("Self", cls._instance)

    def __init__(
        self,
        *,
        config: AgentYmlConfig,
        secrets: Secrets,
        config_path: Path,
    ) -> None:
        """Initialize the Settings instance.

        Args:
            config: The agent.yml config.
            secrets: The environment secrets.
            config_path: The path to the agent.yml config.
        """
        if hasattr(self, "config"):
            return
        self.config = config
        self.secrets = secrets
        self.config_path = config_path

    @property
    def agent(self) -> AgentConfig:
        """The agent configuration."""
        return self.config.agent

    @property
    def protocols(self) -> ProtocolsConfig:
        """The protocol configurations."""
        return self.config.protocols

    @property
    def runtime(self) -> RuntimeConfig:
        """The runtime configuration."""
        return self.config.runtime

    def postgres_conninfo(self, application_name: str | None = None) -> str:
        """Build a libpq connection string from POSTGRES_* secrets.

        Returns:
            Space-separated libpq connection string.
        """
        secrets = self.secrets
        parts = [
            f"host={secrets.POSTGRES_HOST}",
            f"port={secrets.POSTGRES_PORT}",
            f"dbname={secrets.POSTGRES_DATABASE}",
            f"user={secrets.POSTGRES_USER}",
            f"password={secrets.POSTGRES_PASSWORD}",
        ]
        if application_name:
            parts.append(f"application_name={application_name}")
        return " ".join(parts)

    def processing_ttl_seconds(self) -> int:
        """Max processing lease across protocol limits and coordinator default.

        Returns:
            Processing TTL in seconds.
        """
        coordinator = self.runtime.coordinator
        return max(
            self.protocols.chat.maximum_processing_time_seconds,
            self.protocols.payment.maximum_processing_time_seconds,
            coordinator.processing_ttl_seconds,
        )

    def fet_lcd_url(self) -> str:
        """FET LCD REST base URL (env override or network default).

        Returns:
            Base URL without trailing slash.
        """
        override = self.secrets.FET_LCD_URL
        if override and override.strip():
            return override.strip().rstrip("/")
        if self.runtime.network == "testnet":
            return "https://rest-dorado.fetch.ai"
        return "https://rest-fetchhub.fetch.ai"

    @classmethod
    def load(cls, config_path: Path | None = None) -> Settings:
        """Load agent.yml and secrets from the environment.

        Args:
            config_path: The path to the agent.yml config.

        Returns:
            The cached Settings instance.

        Raises:
            SettingsError: If the config file is not found
                            or does not contain a mapping.
        """
        if cls._instance is not None:
            return cls._instance

        path = config_path or DEFAULT_AGENT_YML
        if not path.is_file():
            msg = f"Config file not found: {path}"
            raise SettingsError(msg)

        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)

        if not isinstance(raw_config, dict):
            msg = f"Config file must contain a mapping: {path}"
            raise SettingsError(msg)

        config = AgentYmlConfig.model_validate(raw_config)
        secrets = Secrets()
        return cls(config=config, secrets=secrets, config_path=path)


def get_settings(config_path: Path | None = None) -> Settings:
    """Return the cached Settings instance, loading it on first access."""
    return Settings.load(config_path=config_path)
