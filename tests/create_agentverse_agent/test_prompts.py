"""Tests for the prompts module."""

from __future__ import annotations

import pytest

from create_agentverse_agent import prompts
from create_agentverse_agent.context import PaymentMethodState, ProjectContext


class TestPromptHelpers:
    def test_prompt_int_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prompts, "prompt_with_style", lambda *_a, **_k: "42")
        assert prompts.prompt_int("n", default=1) == 42

    def test_prompt_choice_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prompts.Prompt, "ask", lambda *_a, **_k: "testnet")
        result = prompts.prompt_choice(
            "network", ["testnet", "mainnet"], default="testnet"
        )
        assert result == "testnet"

    def test_prompt_handle_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prompts, "prompt_with_style", lambda *_a, **_k: "my-agent")
        assert prompts.prompt_handle("handle", "default") == "my-agent"


class TestCollectConfiguration:
    def test_default_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prompts.console, "clear", lambda: None)
        monkeypatch.setattr(prompts.console, "print", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "display_summary", lambda *_a: None)
        monkeypatch.setattr(prompts, "success", lambda *_a: None)
        config = prompts.collect_configuration(default=True, advanced=False)
        assert isinstance(config, ProjectContext)
        assert config.yml.runtime.network == "testnet"

    def test_user_abort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(prompts.console, "clear", lambda: None)
        monkeypatch.setattr(prompts.console, "print", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_identity", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_network", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_postgres", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_agentverse", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_payment_methods", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_advanced_runtime", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "display_summary", lambda *_a: None)
        monkeypatch.setattr(prompts.Confirm, "ask", lambda *_a, **_k: False)
        with pytest.raises(prompts.UserAbortError):
            prompts.collect_configuration(default=False, advanced=False)

    def test_payment_methods_stripe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = ProjectContext.create_default()
        monkeypatch.setattr(
            prompts,
            "prompt_choice",
            lambda *_a, **_k: "enabled",
        )
        monkeypatch.setattr(
            prompts,
            "prompt_with_style",
            lambda *_a, password=False, **_k: "secret",
        )
        monkeypatch.setattr(prompts.console, "print", lambda *_a, **_k: None)
        prompts.collect_payment_methods(config, skip=False)
        assert config.yml.protocols.payment.methods.stripe is PaymentMethodState.ENABLED
        assert config.secrets.stripe_secret_key == "secret"
