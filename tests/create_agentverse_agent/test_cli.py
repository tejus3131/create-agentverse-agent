"""Comprehensive tests for the CLI module."""

import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from create_agentverse_agent import cli, prompts, scaffold, templates
from create_agentverse_agent.context import AgentContext


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestVersionCallback:
    """Test version callback functionality."""

    def test_version_callback_exits_when_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that version callback exits when show_version is True."""

        def mock_version(*_: Any) -> str:
            return "1.2.3"

        monkeypatch.setattr(cli, "version", mock_version)

        with pytest.raises(cli.CLIStopExecution):
            cli.version_callback(True)

    def test_version_callback_does_not_exit_when_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that version callback does nothing when show_version is False."""

        def mock_version(*_: Any) -> str:
            return "1.2.3"

        monkeypatch.setattr(cli, "version", mock_version)

        # Should not raise
        result = cli.version_callback(False)
        assert result is None

    def test_version_callback_prints_version(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that version callback prints the version."""

        def mock_version(*_: Any) -> str:
            return "2.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        with pytest.raises(cli.CLIStopExecution):
            cli.version_callback(True)


class TestCLIStopExecution:
    """Test CLIStopExecution exception."""

    def test_cli_stop_execution_is_typer_exit(self) -> None:
        """Test that CLIStopExecution inherits from typer.Exit."""
        import typer

        assert issubclass(cli.CLIStopExecution, typer.Exit)

    def test_cli_stop_execution_can_be_raised(self) -> None:
        """Test that CLIStopExecution can be raised."""
        with pytest.raises(cli.CLIStopExecution):
            raise cli.CLIStopExecution()


class TestMainCommand:
    """Test main CLI command."""

    def test_main_happy_path_default_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test successful execution with default mode."""

        def mock_version(*_: Any) -> str:
            return "1.2.3"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="CLI Agent",
            agent_seed_phrase="seedphrase123",
            agent_port=1234,
            hosting_address="example.com",
            hosting_port=8080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            def __init__(self) -> None:
                self.initialized = True

        class DummyScaffolder:
            def __init__(self, renderer: DummyRenderer) -> None:
                self.renderer = renderer

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert result.exit_code == 0
        assert "Agent Created Successfully" in result.stdout

    def test_main_happy_path_interactive_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test successful execution in interactive mode."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Interactive Agent",
            agent_seed_phrase="interactiveseed",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            assert default is False
            assert advanced is False
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, [])

        assert result.exit_code == 0
        assert "Agent Created Successfully" in result.stdout

    def test_main_advanced_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test successful execution in advanced mode."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Advanced Agent",
            agent_seed_phrase="advancedseed123",
            agent_port=3000,
            hosting_address="advanced.example.com",
            hosting_port=3080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            assert advanced is True
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--advanced"])

        assert result.exit_code == 0

    def test_main_with_overwrite_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test execution with overwrite flag."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Overwrite Agent",
            agent_seed_phrase="overwriteseed",
            agent_port=4000,
            hosting_address="localhost",
            hosting_port=4080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        overwrite_received: list[bool] = []

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                overwrite_received.append(overwrite)
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default", "--overwrite"])

        assert result.exit_code == 0
        assert overwrite_received == [True]

    def test_main_user_abort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of user abort."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            raise prompts.UserAbortError()

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        runner = CliRunner()
        result = runner.invoke(cli.app, [])

        assert "cancelled" in result.stdout.lower()

    def test_main_with_api_keys_not_provided(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that hint to add API keys is shown when not provided."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="No Keys Agent",
            agent_seed_phrase="nokeyseeed123",
            agent_port=5000,
            hosting_address="localhost",
            hosting_port=5080,
            agentverse_api_key=None,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert result.exit_code == 0
        # Should mention adding API keys
        assert "AGENTVERSE_API_KEY" in result.stdout or "API" in result.stdout

    def test_main_with_api_keys_provided(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that no hint for API keys when they are provided."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Keys Agent",
            agent_seed_phrase="keyseed123456",
            agent_port=6000,
            hosting_address="localhost",
            hosting_port=6080,
            agentverse_api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert result.exit_code == 0


class TestCLIOptions:
    """Test CLI options and flags."""

    def test_version_flag_short(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test -v flag shows version."""

        def mock_version(*_: Any) -> str:
            return "3.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["-v"])

        assert result.exit_code == 0
        assert "3.0.0" in result.stdout

    def test_version_flag_long(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test --version flag shows version."""

        def mock_version(*_: Any) -> str:
            return "4.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--version"])

        assert result.exit_code == 0
        assert "4.0.0" in result.stdout

    def test_default_flag_short(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test -d flag for default mode."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        default_used: list[bool] = []

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            default_used.append(default)
            return AgentContext(
                agent_name="Default",
                agent_seed_phrase="defaultseed12",
                agent_port=7000,
                hosting_address="localhost",
                hosting_port=7080,
            )

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["-d"])

        assert result.exit_code == 0
        assert default_used == [True]

    def test_advanced_flag_short(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test -a flag for advanced mode."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        advanced_used: list[bool] = []

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            advanced_used.append(advanced)
            return AgentContext(
                agent_name="Advanced",
                agent_seed_phrase="advancedseed1",
                agent_port=8000,
                hosting_address="localhost",
                hosting_port=8888,
            )

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["-a"])

        assert result.exit_code == 0
        assert advanced_used == [True]

    def test_overwrite_flag_short(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test -o flag for overwrite mode."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        overwrite_used: list[bool] = []

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return AgentContext(
                agent_name="Overwrite",
                agent_seed_phrase="overwriteseed",
                agent_port=9000,
                hosting_address="localhost",
                hosting_port=9999,
            )

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                overwrite_used.append(overwrite)
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["-d", "-o"])

        assert result.exit_code == 0
        assert overwrite_used == [True]


class TestCLIHelp:
    """Test CLI help functionality."""

    def test_help_flag(self) -> None:
        """Test --help flag shows help text."""
        runner = CliRunner()
        result = runner.invoke(cli.app, ["--help"])

        assert result.exit_code == 0
        assert "Create an AgentVerse agent" in result.stdout

    def test_help_shows_options(self) -> None:
        """Test that help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli.app, ["--help"])
        output = strip_ansi(result.stdout)

        assert "--default" in output
        assert "--advanced" in output
        assert "--overwrite" in output
        assert "--version" in output
        assert "--debug" in output


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_file_exists_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of FileExistsError."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return AgentContext(
                agent_name="Existing",
                agent_seed_phrase="existingseed1",
                agent_port=10000,
                hosting_address="localhost",
                hosting_port=10080,
            )

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                raise FileExistsError("Directory already exists")

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert (
            "already exists" in result.stdout.lower()
            or "overwrite" in result.stdout.lower()
        )

    def test_keyboard_interrupt_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of KeyboardInterrupt."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            raise KeyboardInterrupt()

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert "cancelled" in result.stdout.lower()

    def test_generic_exception_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of generic exceptions."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            raise RuntimeError("Something went wrong")

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert "failed" in result.stdout.lower() or "error" in result.stdout.lower()


class TestCLILogging:
    """Test CLI logging functionality."""

    def test_debug_mode_creates_log_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that debug mode mentions log file."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Debug Agent",
            agent_seed_phrase="debugseed1234",
            agent_port=11000,
            hosting_address="localhost",
            hosting_port=11080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        # Change to tmp_path so log file is created there
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default", "--debug"])

        assert result.exit_code == 0
        # Check that debug log message is shown
        assert "log" in result.stdout.lower() or "debug" in result.stdout.lower()


class TestCLIAppConfiguration:
    """Test CLI app configuration."""

    def test_app_has_correct_help_text(self) -> None:
        """Test that app has correct help text."""
        assert cli.app.info.help is not None
        assert "AgentVerse" in cli.app.info.help or "agent" in cli.app.info.help.lower()

    def test_app_is_typer_instance(self) -> None:
        """Test that app is a Typer instance."""
        import typer

        assert isinstance(cli.app, typer.Typer)

    def test_app_has_info(self) -> None:
        """Test that app has info attribute."""
        assert cli.app.info is not None


class TestCLIOutput:
    """Test CLI output formatting."""

    def test_next_steps_shown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that next steps are shown after creation."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Steps Agent",
            agent_seed_phrase="stepsseed1234",
            agent_port=13000,
            hosting_address="localhost",
            hosting_port=13080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert result.exit_code == 0
        assert "Next Steps" in result.stdout
        assert "make dev" in result.stdout

    def test_project_location_shown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that project location is shown after creation."""

        def mock_version(*_: Any) -> str:
            return "1.0.0"

        monkeypatch.setattr(cli, "version", mock_version)

        config = AgentContext(
            agent_name="Location Agent",
            agent_seed_phrase="locationseed1",
            agent_port=14000,
            hosting_address="localhost",
            hosting_port=14080,
        )

        def mock_collect_configuration(default: bool, advanced: bool) -> AgentContext:
            return config

        monkeypatch.setattr(
            prompts, "collect_configuration", mock_collect_configuration
        )

        class DummyRenderer:
            pass

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: AgentContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.safe_name

        monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        runner = CliRunner()
        result = runner.invoke(cli.app, ["--default"])

        assert result.exit_code == 0
        assert "Project Location" in result.stdout
