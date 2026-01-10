from typing import Any

import pytest

from create_agentverse_agent import prompts
from create_agentverse_agent.context import AgentContext


def test_prompt_int_converts_input(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_prompt_with_style(*_: Any, **__: Any) -> str:
        return "123"

    monkeypatch.setattr(prompts, "_prompt_with_style", mock_prompt_with_style)

    # pyright: ignore[reportPrivateUsage]
    result = prompts._prompt_int("Port", default=8080)

    assert result == 123


def test_prompt_choice_accepts_valid_option(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_ask(*_: Any, **__: Any) -> str:
        return "Production"

    monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

    result = prompts._prompt_choice(  # pyright: ignore[reportPrivateUsage]
        "Environment?", choices=["development", "production"], default="development"
    )

    assert result == "production"


def test_collect_configuration_default_mode(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_clear(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(prompts.console, "clear", mock_clear)

    config = prompts.collect_configuration(default=True, advanced=False)

    assert isinstance(config, AgentContext)
    assert config.env == "development"


def test_collect_configuration_user_abort(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_collect_agent_info(*_: Any, **__: Any) -> None:
        return None

    def mock_collect_hosting_info(*_: Any, **__: Any) -> None:
        return None

    def mock_collect_environment_and_keys(*_: Any, **__: Any) -> None:
        return None

    def mock_display_summary(*_: Any, **__: Any) -> None:
        return None

    def mock_ask(*_: Any, **__: Any) -> bool:
        return False

    monkeypatch.setattr(prompts, "_collect_agent_info", mock_collect_agent_info)
    monkeypatch.setattr(prompts, "_collect_hosting_info", mock_collect_hosting_info)
    monkeypatch.setattr(
        prompts, "_collect_environment_and_keys", mock_collect_environment_and_keys
    )
    monkeypatch.setattr(prompts, "_display_summary", mock_display_summary)

    monkeypatch.setattr(prompts.Confirm, "ask", mock_ask)

    with pytest.raises(prompts.UserAbortError):
        prompts.collect_configuration(default=False, advanced=False)


def test_collect_configuration_advanced_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[bool]] = {
        "agent": [],
        "hosting": [],
        "env": [],
    }

    responses = iter([True, False, True])

    def mock_agent_info(config: AgentContext, skip: bool = False) -> None:
        calls["agent"].append(skip)

    def mock_hosting_info(config: AgentContext, skip: bool = False) -> None:
        calls["hosting"].append(skip)

    def mock_env_info(config: AgentContext, skip: bool = False) -> None:
        calls["env"].append(skip)

    def mock_display_summary(*_: Any, **__: Any) -> None:
        return None

    def mock_ask(*_: Any, **__: Any) -> bool:
        return next(responses)

    def mock_clear(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(prompts, "_collect_agent_info", mock_agent_info)
    monkeypatch.setattr(prompts, "_collect_hosting_info", mock_hosting_info)
    monkeypatch.setattr(prompts, "_collect_environment_and_keys", mock_env_info)
    monkeypatch.setattr(prompts, "_display_summary", mock_display_summary)
    monkeypatch.setattr(prompts.Confirm, "ask", mock_ask)
    monkeypatch.setattr(prompts.console, "clear", mock_clear)

    config = prompts.collect_configuration(default=False, advanced=True)

    assert isinstance(config, AgentContext)
    assert calls["agent"] == [False]
    assert calls["hosting"] == [False]
    assert calls["env"] == [True]
