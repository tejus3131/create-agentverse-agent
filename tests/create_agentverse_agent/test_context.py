"""Tests for ProjectContext and related configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from create_agentverse_agent.context import (
    ContextError,
    PaymentMethodState,
    ProjectContext,
    default_yml_config,
    parse_window_seconds,
)


class TestDefaults:
    def test_create_default_context(self) -> None:
        config = ProjectContext.create_default()
        assert config.yml.agent.port == 8000
        assert config.yml.runtime.network == "testnet"
        assert config.secrets.postgres_host == "localhost"
        assert config.project_name == config.yml.agent.handle

    def test_payment_defaults_disable_stripe_skyfire(self) -> None:
        config = ProjectContext.create_default()
        methods = config.yml.protocols.payment.methods
        assert methods.fet is PaymentMethodState.ENABLED
        assert methods.stripe is PaymentMethodState.DISABLED
        assert methods.skyfire is PaymentMethodState.DISABLED

    def test_default_avatar_and_banner_urls(self) -> None:
        from create_agentverse_agent.context import (
            DEFAULT_AVATAR_URL,
            DEFAULT_BANNER_URL,
        )

        config = ProjectContext.create_default()
        assert config.yml.agent.avatar_url == DEFAULT_AVATAR_URL
        assert config.yml.agent.banner_url == DEFAULT_BANNER_URL


class TestHandleValidation:
    def test_invalid_handle_rejected(self) -> None:
        with pytest.raises(ValidationError):
            default_yml_config(handle="Invalid Handle")

    def test_valid_handle(self) -> None:
        yml = default_yml_config(handle="my-agent-123")
        assert yml.agent.handle == "my-agent-123"


class TestPaymentCrossValidation:
    def test_stripe_enabled_requires_keys(self) -> None:
        config = ProjectContext.create_default()
        config.yml.protocols.payment.methods.stripe = PaymentMethodState.ENABLED
        with pytest.raises(ContextError):
            config.revalidated()

    def test_stripe_enabled_with_keys(self) -> None:
        config = ProjectContext.create_default()
        config.yml.protocols.payment.methods.stripe = PaymentMethodState.ENABLED
        config.secrets.stripe_secret_key = "sk_test_abc"
        config.secrets.stripe_publishable_key = "pk_test_abc"
        validated = config.revalidated()
        assert validated.secrets.stripe_secret_key == "sk_test_abc"

    def test_skyfire_enabled_requires_keys(self) -> None:
        config = ProjectContext.create_default()
        config.yml.protocols.payment.methods.skyfire = PaymentMethodState.ENABLED
        with pytest.raises(ContextError):
            config.revalidated()


class TestWindowParsing:
    def test_parse_seconds(self) -> None:
        assert parse_window_seconds("30s") == 30

    def test_parse_minutes(self) -> None:
        assert parse_window_seconds("2m") == 120

    def test_invalid_window(self) -> None:
        with pytest.raises(ContextError):
            parse_window_seconds("bad")


class TestComputedProperties:
    def test_project_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        import pathlib

        monkeypatch.chdir(pathlib.Path(str(tmp_path)))
        config = ProjectContext.create_default()
        assert config.project_path.name == config.project_name

    def test_model_dump_includes_nested(self) -> None:
        config = ProjectContext.create_default()
        data = config.model_dump()
        assert "agent" in data
        assert "secrets" in data
        assert "yml" in data
        assert data["secrets"]["postgres_host"] == "localhost"

    def test_repr_hides_secrets(self) -> None:
        config = ProjectContext.create_default()
        text = repr(config)
        assert config.secrets.postgres_password not in text
