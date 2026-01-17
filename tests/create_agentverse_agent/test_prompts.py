"""Comprehensive tests for the prompts module."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from create_agentverse_agent import prompts
from create_agentverse_agent.context import AgentContext


class TestPromptWithStyle:
    """Test prompt_with_style function."""

    def test_returns_user_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that user input is returned."""

        def mock_ask(*_: Any, **__: Any) -> str:
            return "user input"

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        result = prompts.prompt_with_style("Test prompt")

        assert result == "user input"

    def test_with_default_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test prompt with default value."""
        received_default: list[str | None] = []

        def mock_ask(*_: Any, default: str | None = None, **__: Any) -> str:
            received_default.append(default)
            return default or "input"

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        prompts.prompt_with_style("Test", default="default_value")

        assert received_default == ["default_value"]

    def test_password_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test prompt in password mode."""
        received_password: list[bool] = []

        def mock_ask(*_: Any, password: bool = False, **__: Any) -> str:
            received_password.append(password)
            return "secret"

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        prompts.prompt_with_style("Password", password=True)

        assert received_password == [True]

    def test_empty_input_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty input returns empty string when no default."""

        def mock_ask(*_: Any, **__: Any) -> str:
            return ""

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        result = prompts.prompt_with_style("Test")

        assert result == ""


class TestPromptInt:
    """Test prompt_int function."""

    def test_converts_valid_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that valid integer input is converted."""

        def mock_prompt_with_style(*_: Any, **__: Any) -> str:
            return "123"

        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)

        result = prompts.prompt_int("Port", default=8080)

        assert result == 123
        assert isinstance(result, int)

    def test_uses_default_when_shown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default value is displayed."""
        received_defaults: list[str] = []

        def mock_prompt_with_style(
            prompt: str, default: str | None = None, **__: Any
        ) -> str:
            received_defaults.append(default or "")
            return default or "0"

        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)

        prompts.prompt_int("Port", default=9999)

        assert received_defaults == ["9999"]

    def test_retries_on_invalid_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid input causes retry."""
        call_count = [0]
        responses = ["invalid", "abc", "42"]

        def mock_prompt_with_style(*_: Any, **__: Any) -> str:
            response = responses[call_count[0]]
            call_count[0] += 1
            return response

        mock_print = MagicMock()
        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        result = prompts.prompt_int("Number", default=0)

        assert result == 42
        assert call_count[0] == 3

    def test_handles_negative_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that negative numbers are handled."""

        def mock_prompt_with_style(*_: Any, **__: Any) -> str:
            return "-100"

        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)

        result = prompts.prompt_int("Number", default=0)

        assert result == -100

    def test_handles_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that zero is handled."""

        def mock_prompt_with_style(*_: Any, **__: Any) -> str:
            return "0"

        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)

        result = prompts.prompt_int("Number", default=1)

        assert result == 0


class TestPromptChoice:
    """Test prompt_choice function."""

    def test_accepts_valid_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that valid choice is accepted."""

        def mock_ask(*_: Any, **__: Any) -> str:
            return "production"

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        result = prompts.prompt_choice(
            "Environment?",
            choices=["development", "production"],
            default="development",
        )

        assert result == "production"

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that choice matching is case insensitive."""

        def mock_ask(*_: Any, **__: Any) -> str:
            return "Production"

        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)

        result = prompts.prompt_choice(
            "Environment?",
            choices=["development", "production"],
            default="development",
        )

        assert result == "production"

    def test_retries_on_invalid_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid choice causes retry."""
        call_count = [0]
        responses = ["invalid", "bad", "development"]

        def mock_ask(*_: Any, **__: Any) -> str:
            response = responses[call_count[0]]
            call_count[0] += 1
            return response

        mock_print = MagicMock()
        monkeypatch.setattr(prompts.Prompt, "ask", mock_ask)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        result = prompts.prompt_choice(
            "Environment?",
            choices=["development", "production"],
            default="development",
        )

        assert result == "development"
        assert call_count[0] == 3


class TestHelperFunctions:
    """Test helper display functions."""

    def test_header_displays_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that header displays text."""
        printed: list[str] = []

        def mock_print(text: str = "") -> None:
            printed.append(text)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.header("Test Header")

        assert any("Test Header" in str(p) for p in printed)

    def test_header_with_custom_emoji(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test header with custom emoji."""
        printed: list[str] = []

        def mock_print(text: str = "") -> None:
            printed.append(text)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.header("Custom", emoji="🎉")

        assert any("🎉" in str(p) for p in printed)

    def test_success_displays_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that success displays message."""
        printed: list[str] = []

        def mock_print(text: str = "") -> None:
            printed.append(text)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.success("Success message")

        assert any("Success message" in str(p) for p in printed)

    def test_hint_displays_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that hint displays message."""
        printed: list[str] = []

        def mock_print(text: str = "") -> None:
            printed.append(text)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.hint("Hint message")

        assert any("Hint message" in str(p) for p in printed)

    def test_divider_prints_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that divider prints separator line."""
        printed: list[str] = []

        def mock_print(text: str = "") -> None:
            printed.append(text)

        monkeypatch.setattr(prompts.console, "print", mock_print)
        monkeypatch.setattr(prompts.console, "width", 80)

        prompts.divider()

        # Should have printed at least the divider
        assert len(printed) >= 1


class TestCollectAgentInfo:
    """Test collect_agent_info function."""

    def test_skips_when_skip_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that prompts are skipped when skip=True."""
        config = AgentContext()
        original_name = config.agent_name

        mock_success = MagicMock()
        monkeypatch.setattr(prompts, "success", mock_success)

        prompts.collect_agent_info(config, skip=True)

        # Name should remain unchanged
        assert config.agent_name == original_name
        mock_success.assert_called_once()

    def test_collects_info_when_not_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that info is collected when not skipped."""
        config = AgentContext()

        call_order: list[str] = []

        def mock_header(*_: Any, **__: Any) -> None:
            call_order.append("header")

        def mock_hint(*_: Any, **__: Any) -> None:
            call_order.append("hint")

        def mock_prompt(
            prompt: str, default: str | None = None, password: bool = False
        ) -> str:
            call_order.append(f"prompt:{prompt[:20]}")
            if password:
                return "newseedphrase12345"
            return default or "value"

        def mock_prompt_int(prompt: str, default: int) -> int:
            call_order.append(f"prompt_int:{prompt[:20]}")
            return default

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "header", mock_header)
        monkeypatch.setattr(prompts, "hint", mock_hint)
        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt)
        monkeypatch.setattr(prompts, "prompt_int", mock_prompt_int)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.collect_agent_info(config, skip=False)

        assert "header" in call_order


class TestCollectHostingInfo:
    """Test collect_hosting_info function."""

    def test_skips_when_skip_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that prompts are skipped when skip=True."""
        config = AgentContext()
        original_address = config.hosting_address

        mock_success = MagicMock()
        monkeypatch.setattr(prompts, "success", mock_success)

        prompts.collect_hosting_info(config, skip=True)

        assert config.hosting_address == original_address
        mock_success.assert_called_once()

    def test_collects_info_when_not_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that hosting info is collected when not skipped."""
        config = AgentContext()
        original_address = config.hosting_address

        def mock_header(*_: Any, **__: Any) -> None:
            pass

        def mock_hint(*_: Any, **__: Any) -> None:
            pass

        def mock_prompt_with_style(
            prompt: str, default: str | None = None, **__: Any
        ) -> str:
            return "custom-address"

        def mock_prompt_int(prompt: str, default: int) -> int:
            return 999

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "header", mock_header)
        monkeypatch.setattr(prompts, "hint", mock_hint)
        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)
        monkeypatch.setattr(prompts, "prompt_int", mock_prompt_int)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.collect_hosting_info(config, skip=False)

        # Address should be set by mock
        assert config.hosting_address == "custom-address"
        assert config.hosting_address != original_address
        # Port should be set to 999 by mock
        assert config.hosting_port == 999


class TestCollectAdvancedSettings:
    """Test collect_hosting_info function."""

    def test_skips_when_skip_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that prompts are skipped when skip=True."""
        config = AgentContext()
        original_max = config.max_processed_messages

        mock_success = MagicMock()
        monkeypatch.setattr(prompts, "success", mock_success)

        prompts.collect_hosting_info(config, skip=True)

        assert config.max_processed_messages == original_max
        mock_success.assert_called_once()

    def test_collects_settings_when_not_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that advanced settings are collected when not skipped."""
        config = AgentContext()

        prompt_int_calls: list[int] = []

        def mock_header(*_: Any, **__: Any) -> None:
            pass

        def mock_hint(*_: Any, **__: Any) -> None:
            pass

        def mock_prompt_int(prompt: str, default: int) -> int:
            prompt_int_calls.append(default)
            return default * 2  # Return doubled value to verify it's used

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "header", mock_header)
        monkeypatch.setattr(prompts, "hint", mock_hint)
        monkeypatch.setattr(prompts, "prompt_int", mock_prompt_int)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.collect_advanced_info(config, skip=False)

        # Should have prompted for multiple settings (5 int prompts in collect_advanced_info)
        assert len(prompt_int_calls) >= 4


class TestCollectEnvironmentAndKeys:
    """Test collect_environment_and_keys function."""

    def test_skips_when_skip_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that prompts are skipped when skip=True."""
        config = AgentContext()
        original_env = config.env

        mock_success = MagicMock()
        monkeypatch.setattr(prompts, "success", mock_success)

        prompts.collect_environment_and_keys(config, skip=True)

        assert config.env == original_env
        mock_success.assert_called_once()

    def test_collects_env_when_not_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment is collected when not skipped."""
        config = AgentContext()

        def mock_header(*_: Any, **__: Any) -> None:
            pass

        def mock_hint(*_: Any, **__: Any) -> None:
            pass

        def mock_prompt_choice(prompt: str, choices: list[str], default: str) -> str:
            return "production"

        def mock_confirm(*_: Any, **__: Any) -> bool:
            return False  # Don't add API key

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "header", mock_header)
        monkeypatch.setattr(prompts, "hint", mock_hint)
        monkeypatch.setattr(prompts, "prompt_choice", mock_prompt_choice)
        monkeypatch.setattr(prompts.Confirm, "ask", mock_confirm)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.collect_environment_and_keys(config, skip=False)

        assert config.env == "production"

    def test_collects_api_key_when_confirmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that API key is collected when user confirms."""
        config = AgentContext()

        def mock_header(*_: Any, **__: Any) -> None:
            pass

        def mock_hint(*_: Any, **__: Any) -> None:
            pass

        def mock_prompt_choice(prompt: str, choices: list[str], default: str) -> str:
            return "development"

        def mock_confirm(*_: Any, **__: Any) -> bool:
            return True  # Add API key

        def mock_prompt_with_style(
            prompt: str, password: bool = False, **__: Any
        ) -> str:
            return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "header", mock_header)
        monkeypatch.setattr(prompts, "hint", mock_hint)
        monkeypatch.setattr(prompts, "prompt_choice", mock_prompt_choice)
        monkeypatch.setattr(prompts.Confirm, "ask", mock_confirm)
        monkeypatch.setattr(prompts, "prompt_with_style", mock_prompt_with_style)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.collect_environment_and_keys(config, skip=False)

        assert config.agentverse_api_key is not None


class TestDisplaySummary:
    """Test display_summary function."""

    def test_displays_all_sections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that summary displays all configuration sections."""
        config = AgentContext(
            agent_name="Test Agent",
            agent_seed_phrase="testseed12345678",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
            env="development",
        )

        printed_items: list[Any] = []

        def mock_print(item: Any = "") -> None:
            printed_items.append(item)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.display_summary(config)

        # Should have printed something
        assert len(printed_items) > 0

    def test_displays_api_key_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that summary displays truncated API key when set."""
        config = AgentContext(
            agent_name="Test Agent",
            agent_seed_phrase="testseed12345678",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
            env="development",
            agentverse_api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        )

        printed_items: list[Any] = []

        def mock_print(item: Any = "") -> None:
            printed_items.append(item)

        monkeypatch.setattr(prompts.console, "print", mock_print)

        prompts.display_summary(config)

        # Should have printed something
        assert len(printed_items) > 0


class TestCollectConfiguration:
    """Test collect_configuration main function."""

    def test_default_mode_returns_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default mode returns config without prompts."""

        def mock_clear(*_: Any, **__: Any) -> None:
            pass

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        def mock_display_summary(*_: Any, **__: Any) -> None:
            pass

        def mock_success(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts.console, "clear", mock_clear)
        monkeypatch.setattr(prompts.console, "print", mock_print)
        monkeypatch.setattr(prompts, "display_summary", mock_display_summary)
        monkeypatch.setattr(prompts, "success", mock_success)

        config = prompts.collect_configuration(default=True, advanced=False)

        assert isinstance(config, AgentContext)
        assert config.env == "development"

    def test_user_abort_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that user abort raises UserAbortError."""

        def mock_collect_agent_info(*_: Any, **__: Any) -> None:
            pass

        def mock_collect_hosting_info(*_: Any, **__: Any) -> None:
            pass

        def mock_collect_environment_and_keys(*_: Any, **__: Any) -> None:
            pass

        def mock_display_summary(*_: Any, **__: Any) -> None:
            pass

        def mock_confirm(*_: Any, **__: Any) -> bool:
            return False

        def mock_clear(*_: Any, **__: Any) -> None:
            pass

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "collect_agent_info", mock_collect_agent_info)
        monkeypatch.setattr(prompts, "collect_hosting_info", mock_collect_hosting_info)
        monkeypatch.setattr(
            prompts, "collect_environment_and_keys", mock_collect_environment_and_keys
        )
        monkeypatch.setattr(prompts, "display_summary", mock_display_summary)
        monkeypatch.setattr(prompts.Confirm, "ask", mock_confirm)
        monkeypatch.setattr(prompts.console, "clear", mock_clear)
        monkeypatch.setattr(prompts.console, "print", mock_print)

        with pytest.raises(prompts.UserAbortError):
            prompts.collect_configuration(default=False, advanced=False)

    def test_advanced_mode_prompts_for_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that advanced mode prompts for additional options."""
        confirm_calls: list[str] = []
        confirm_responses = iter([True, True, True, True])

        def mock_collect_agent_info(config: AgentContext, skip: bool = False) -> None:
            pass

        def mock_collect_hosting_info(config: AgentContext, skip: bool = False) -> None:
            pass

        def mock_collect_environment_and_keys(
            config: AgentContext, skip: bool = False
        ) -> None:
            pass

        def mock_collect_advanced_info(
            config: AgentContext, skip: bool = False
        ) -> None:
            pass

        def mock_display_summary(*_: Any, **__: Any) -> None:
            pass

        def mock_divider() -> None:
            pass

        def mock_confirm(prompt: str, *_: Any, **__: Any) -> bool:
            confirm_calls.append(prompt)
            return next(confirm_responses)

        def mock_clear(*_: Any, **__: Any) -> None:
            pass

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        def mock_success(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "collect_agent_info", mock_collect_agent_info)
        monkeypatch.setattr(prompts, "collect_hosting_info", mock_collect_hosting_info)
        monkeypatch.setattr(
            prompts, "collect_environment_and_keys", mock_collect_environment_and_keys
        )
        monkeypatch.setattr(
            prompts, "collect_advanced_info", mock_collect_advanced_info
        )
        monkeypatch.setattr(prompts, "display_summary", mock_display_summary)
        monkeypatch.setattr(prompts, "divider", mock_divider)
        monkeypatch.setattr(prompts.Confirm, "ask", mock_confirm)
        monkeypatch.setattr(prompts.console, "clear", mock_clear)
        monkeypatch.setattr(prompts.console, "print", mock_print)
        monkeypatch.setattr(prompts, "success", mock_success)

        config = prompts.collect_configuration(default=False, advanced=True)

        assert isinstance(config, AgentContext)
        # Should have asked multiple confirmation questions
        assert len(confirm_calls) >= 3

    def test_standard_mode_skips_advanced_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that standard mode skips advanced configuration."""
        hosting_skip_calls: list[bool] = []
        env_skip_calls: list[bool] = []
        advanced_skip_calls: list[bool] = []

        def mock_collect_agent_info(config: AgentContext, skip: bool = False) -> None:
            pass

        def mock_collect_hosting_info(config: AgentContext, skip: bool = False) -> None:
            hosting_skip_calls.append(skip)

        def mock_collect_environment_and_keys(
            config: AgentContext, skip: bool = False
        ) -> None:
            env_skip_calls.append(skip)

        def mock_collect_advanced_info(
            config: AgentContext, skip: bool = False
        ) -> None:
            advanced_skip_calls.append(skip)

        def mock_display_summary(*_: Any, **__: Any) -> None:
            pass

        def mock_confirm(*_: Any, **__: Any) -> bool:
            return True

        def mock_clear(*_: Any, **__: Any) -> None:
            pass

        def mock_print(*_: Any, **__: Any) -> None:
            pass

        def mock_success(*_: Any, **__: Any) -> None:
            pass

        monkeypatch.setattr(prompts, "collect_agent_info", mock_collect_agent_info)
        monkeypatch.setattr(prompts, "collect_hosting_info", mock_collect_hosting_info)
        monkeypatch.setattr(
            prompts, "collect_environment_and_keys", mock_collect_environment_and_keys
        )
        monkeypatch.setattr(
            prompts, "collect_advanced_info", mock_collect_advanced_info
        )
        monkeypatch.setattr(prompts, "display_summary", mock_display_summary)
        monkeypatch.setattr(prompts.Confirm, "ask", mock_confirm)
        monkeypatch.setattr(prompts.console, "clear", mock_clear)
        monkeypatch.setattr(prompts.console, "print", mock_print)
        monkeypatch.setattr(prompts, "success", mock_success)

        prompts.collect_configuration(default=False, advanced=False)

        # In standard mode, all collectors are called once with skip=True
        assert hosting_skip_calls == [True]
        assert env_skip_calls == [True]
        assert advanced_skip_calls == [True]


class TestUserAbortError:
    """Test UserAbortError exception."""

    def test_inherits_from_typer_abort(self) -> None:
        """Test that UserAbortError inherits from typer.Abort."""
        import typer

        assert issubclass(prompts.UserAbortError, typer.Abort)

    def test_can_be_raised(self) -> None:
        """Test that UserAbortError can be raised."""
        with pytest.raises(prompts.UserAbortError):
            raise prompts.UserAbortError()

    def test_can_be_caught_as_typer_abort(self) -> None:
        """Test that UserAbortError can be caught as typer.Abort."""
        import typer

        with pytest.raises(typer.Abort):
            raise prompts.UserAbortError()


class TestConsoleOutput:
    """Test console output functionality."""

    def test_console_is_rich_console(self) -> None:
        """Test that console is a Rich Console instance."""
        from rich.console import Console

        assert isinstance(prompts.console, Console)
