from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from create_agentverse_agent import cli, prompts, scaffold, templates
from create_agentverse_agent.context import AgentContext


def test_version_callback_exits(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_version(*_: Any) -> str:
        return "1.2.3"

    monkeypatch.setattr(cli, "version", mock_version)

    with pytest.raises(cli.CLIStopExecution):
        cli.version_callback(True)


def test_main_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:

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

    monkeypatch.setattr(prompts, "collect_configuration", mock_collect_configuration)

    class DummyRenderer:
        def __init__(self) -> None:
            self.initialized = True

    class DummyScaffolder:
        def __init__(self, renderer: DummyRenderer) -> None:
            self.renderer = renderer

        def create_project(self, ctx: AgentContext, overwrite: bool = False) -> Path:
            return tmp_path / ctx.safe_name

    monkeypatch.setattr(templates, "TemplateRenderer", DummyRenderer)
    monkeypatch.setattr(scaffold, "Scaffolder", DummyScaffolder)

    runner = CliRunner()
    result = runner.invoke(cli.app, ["--default"])

    assert result.exit_code == 0
    assert "Agent Created Successfully" in result.stdout
