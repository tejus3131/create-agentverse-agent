"""Tests for the CLI module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from create_agentverse_agent import cli, prompts, scaffold, templates
from create_agentverse_agent.context import ProjectContext
from create_agentverse_agent.scaffold import ScaffoldError


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestMainCommand:
    def test_default_mode_success(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        config = ProjectContext.create_default()

        monkeypatch.setattr(
            prompts,
            "collect_configuration",
            lambda default, advanced: config,
        )

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                self.renderer = renderer

            def create_project(
                self, ctx: ProjectContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.project_name

        monkeypatch.setattr(templates, "TemplateRenderer", lambda: object())
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        result = CliRunner().invoke(cli.app, ["--default"])
        assert result.exit_code == 0
        assert "Project Created Successfully" in result.stdout
        assert "make test" in result.stdout
        assert "uv sync" in result.stdout

    def test_user_abort_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        monkeypatch.setattr(
            prompts,
            "collect_configuration",
            lambda default, advanced: (_ for _ in ()).throw(prompts.UserAbortError()),
        )
        result = CliRunner().invoke(cli.app, [])
        assert result.exit_code != 0
        assert "cancelled" in result.stdout.lower()

    def test_scaffold_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        monkeypatch.setattr(
            prompts,
            "collect_configuration",
            lambda default, advanced: ProjectContext.create_default(),
        )

        class FailingScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: ProjectContext, overwrite: bool = False
            ) -> Path:
                raise ScaffoldError("Directory already exists")

        monkeypatch.setattr(templates, "TemplateRenderer", lambda: object())
        monkeypatch.setattr(scaffold, "Scaffolder", FailingScaffolder)

        result = CliRunner().invoke(cli.app, ["--default"])
        assert result.exit_code != 0
        assert "overwrite" in result.stdout.lower()

    def test_missing_agentverse_hint(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        config = ProjectContext.create_default()
        config.secrets.agentverse_api_key = None

        monkeypatch.setattr(
            prompts, "collect_configuration", lambda default, advanced: config
        )

        class DummyScaffolder:
            def __init__(self, renderer: Any) -> None:
                pass

            def create_project(
                self, ctx: ProjectContext, overwrite: bool = False
            ) -> Path:
                return tmp_path / ctx.project_name

        monkeypatch.setattr(templates, "TemplateRenderer", lambda: object())
        monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

        result = CliRunner().invoke(cli.app, ["--default"])
        assert "AGENTVERSE_API_KEY" in result.stdout


class TestCLIOptions:
    def test_version_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        result = CliRunner().invoke(cli.app, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.stdout

    def test_help_flag(self) -> None:
        result = CliRunner().invoke(cli.app, ["--help"])
        output = strip_ansi(result.stdout)
        assert "--default" in output
        assert "--advanced" in output
        assert "--overwrite" in output


class TestCLIStopExecution:
    def test_is_typer_exit(self) -> None:
        assert issubclass(cli.CLIStopExecution, typer.Exit)
