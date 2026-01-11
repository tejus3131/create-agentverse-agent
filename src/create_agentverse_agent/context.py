# src/create_agentverse_agent/context.py
import logging
from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class AgentContextError(Exception):
    """Custom exception for port conflicts."""

    pass


class AgentContext(BaseModel):
    """Single source of truth for agent configuration."""

    agent_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9\s]+$",
        title="Agent Name",
        description="The human-readable name of the agent",
        examples=["My Agent", "Test Agent 123"],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    The name of the agent. This should be a human-readable string containing only letters, numbers, and spaces.
    1 to 100 characters in length.
    """

    agent_seed_phrase: str = Field(
        default_factory=lambda: __import__("secrets").token_hex(32),
        min_length=1,
        max_length=500,
        pattern=r"^[a-zA-Z0-9]+$",
        title="Agent Seed Phrase",
        description="A random seed string (alphanumeric, typically 32+ chars)",
        examples=["aB3kL9mN2pQ5rT8vX1yZ4"],
        frozen=False,
        strict=True,
        repr=False,
    )
    """
    A random seed phrase used for agent initialization. Should be URL-safe base64 characters.
    Typically at least 32 characters in length.
    """

    agent_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        title="Agent Port",
        description="The port on which the agent will run",
        examples=[8000, 8001, 9000],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    The port number on which the agent will run. Must be between 1024 and 65535.
    """

    agent_description: str = Field(
        default="An ASI1 compatible agent built using 'create-agentverse-agent'.",
        min_length=1,
        max_length=500,
        title="Agent Description",
        description="A brief description of the agent's purpose",
        examples=["A helpful assistant.", "A weather bot."],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    A brief description of the agent's purpose. 1 to 500 characters in length.
    """

    hosting_address: str = Field(
        default="localhost",
        min_length=1,
        max_length=255,
        title="Hosting Address",
        description="The host address for the hosting service",
        examples=["localhost", "127.0.0.1"],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    The host address where the hosting service will run.
    """

    hosting_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        title="Hosting Port",
        description="The port on which the hosting service will run",
        examples=[8080, 8081, 9080],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    The port number for the hosting service. Must be between 1024 and 65535.
    """

    env: str = Field(
        default="development",
        title="Environment",
        description="The environment in which the agent is running (e.g., production or development)",
        examples=["production", "development"],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    The environment in which the agent is running. Typically 'production' or 'development'.
    """

    agentverse_api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=1000,
        pattern=r"^eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_=]*$",
        title="AgentVerse API Key",
        description="API key for AgentVerse services (JWT format)",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
        frozen=False,
        strict=True,
        repr=False,
    )
    """
    API key for AgentVerse services in JWT format. Must be at least 20 characters long.
    """

    max_processed_messages: int = Field(
        default=1000,
        ge=1,
        title="Max Processed Messages",
        description="Maximum number of processed messages to track",
        examples=[1000, 5000],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    Maximum number of processed messages to keep in memory.
    """

    processed_message_ttl_minutes: int = Field(
        default=60,
        ge=1,
        title="Processed Message TTL",
        description="TTL for processed messages in minutes",
        examples=[60, 120],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    Time-to-live for processed messages in minutes.
    """

    cleanup_interval_seconds: int = Field(
        default=300,
        ge=10,
        title="Cleanup Interval",
        description="Interval for cleanup tasks in seconds",
        examples=[300, 600],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    Interval in seconds for running cleanup tasks.
    """

    rate_limit_max_requests: int = Field(
        default=30,
        ge=1,
        title="Rate Limit Max Requests",
        description="Maximum requests allowed",
        examples=[100, 500],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    Maximum number of requests allowed within the rate limit window.
    """

    rate_limit_window_minutes: int = Field(
        default=60,
        ge=1,
        title="Rate Limit Window",
        description="Rate limit window in minutes",
        examples=[60, 120],
        frozen=False,
        strict=True,
        repr=True,
    )
    """
    Time window in minutes for rate limiting.
    """

    def model_post_init(self, __context: Any) -> None:
        """Log context initialization after model is created."""
        logger.info(
            "AgentContext initialized: name=%s, env=%s", self.display_name, self.env
        )
        logger.debug(
            "Agent configuration: port=%d, hosting=%s:%d",
            self.agent_port,
            self.hosting_address,
            self.hosting_port,
        )
        if self.is_api_keys_provided():
            logger.debug("API keys configured: agentverse=yes")
        else:
            logger.warning(
                "Missing API keys: agentverse=%s",
                "yes" if self.agentverse_api_key else "no",
            )

    @model_validator(mode="after")
    def check_ports_different(self) -> "AgentContext":
        """Ensure agent_port and hosting_port are different."""
        if self.agent_port == self.hosting_port:
            logger.error(
                "Port conflict: agent_port=%d and hosting_port=%d are the same",
                self.agent_port,
                self.hosting_port,
            )
            raise AgentContextError(
                f"Agent port ({self.agent_port}) and hosting port ({self.hosting_port}) must be different."
            )
        return self

    @property
    def display_name(self) -> str:
        """Formatted display name for the agent."""
        return self.agent_name or "Agent " + self.agent_seed_phrase[:8]

    @property
    def safe_name(self) -> str:
        """URL-safe version of the agent name."""
        return self.display_name.lower().replace(" ", "-").replace("_", "-")

    @property
    def project_path(self) -> Path:
        """The filesystem path where the agent project will be created."""
        return Path.cwd() / self.safe_name

    @property
    def agent_route(self) -> str:
        """The URL route for accessing the agent."""
        return f"/{self.safe_name}"

    @property
    def hosting_endpoint(self) -> str:
        """The full URL endpoint for the hosting service."""
        return f"http://{self.hosting_address}:{self.hosting_port}"

    @override
    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Custom model dump to include computed properties."""
        logger.debug("Dumping model for agent: %s", self.display_name)
        data = super().model_dump(**kwargs)
        data.update(
            {
                "display_name": self.display_name,
                "safe_name": self.safe_name,
                "project_path": str(self.project_path),
                "agent_route": self.agent_route,
                "hosting_endpoint": self.hosting_endpoint,
            }
        )
        return data

    def is_api_keys_provided(self) -> bool:
        """Check if both API keys are provided."""
        return bool(self.agentverse_api_key)

    @override
    def __repr__(self) -> str:
        """Custom repr to avoid exposing sensitive fields."""
        fields = ", ".join(
            f"{k}={v!r}"
            for k, v in self.model_dump().items()
            if k not in {"agent_seed_phrase", "agentverse_api_key"}
        )
        return f"{self.__class__.__name__}({fields})"

    def __str__(self) -> str:
        """String representation of the context."""
        return self.__repr__()
