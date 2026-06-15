"""Tests for the scaffold module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from create_agentverse_agent.context import ProjectContext
from create_agentverse_agent.scaffold import Scaffolder, ScaffoldError
from create_agentverse_agent.templates import TemplateRenderer


class TestScaffolder:
    def test_create_project_returns_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = scaffolder.create_project(config)
        assert project_path == tmp_path / config.project_name

    def test_create_project_writes_core_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = scaffolder.create_project(config)

        assert (project_path / "agent.yml").exists()
        assert (project_path / ".env").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "README.md").exists()
        assert (project_path / "AGENTVERSE.md").exists()
        agentverse = (project_path / "AGENTVERSE.md").read_text()
        assert config.yml.agent.handle in agentverse
        assert config.yml.agent.description in agentverse
        assert (project_path / "docker-compose.yml").exists()
        assert (project_path / "schema.sql").exists()
        assert (project_path / "Dockerfile").exists()
        assert (project_path / "Makefile").exists()
        makefile = (project_path / "Makefile").read_text()
        assert "make test" in makefile
        assert (project_path / "src/runtime/agent.py").exists()
        assert (project_path / "src/shared/settings.py").exists()
        assert (project_path / "src/agent/handler.py").exists()
        assert (project_path / "src/agent/__init__.py").exists()

    def test_agent_yml_is_valid(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = scaffolder.create_project(config)
        data = yaml.safe_load((project_path / "agent.yml").read_text())
        assert data["agent"]["handle"] == config.yml.agent.handle
        assert data["agent"]["avatar_url"] == config.yml.agent.avatar_url
        assert data["agent"]["banner_url"] == config.yml.agent.banner_url
        assert data["runtime"]["network"] == "testnet"

    def test_env_contains_postgres_vars(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = scaffolder.create_project(config)
        env_text = (project_path / ".env").read_text()
        assert "POSTGRES_HOST=localhost" in env_text
        assert "POSTGRES_PASSWORD=" in env_text
        assert "AGENT_SEED=" in env_text

    def test_prevents_overwrite_by_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        config.project_path.mkdir(parents=True)
        with pytest.raises(ScaffoldError, match="already exists"):
            scaffolder.create_project(config, overwrite=False)

    def test_allows_overwrite(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = config.project_path
        project_path.mkdir(parents=True)
        stale = project_path / "README.md"
        stale.write_text("stale")
        scaffolder.create_project(config, overwrite=True)
        assert "Quick start" in stale.read_text()

    def test_preserves_extra_files_on_overwrite(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        scaffolder = Scaffolder(TemplateRenderer())
        project_path = config.project_path
        project_path.mkdir(parents=True)
        extra = project_path / "custom.txt"
        extra.write_text("keep me")
        scaffolder.create_project(config, overwrite=True)
        assert extra.read_text() == "keep me"


class TestScaffoldIntegration:
    def test_full_default_scaffold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = ProjectContext.create_default()
        project_path = Scaffolder(TemplateRenderer()).create_project(config)
        assert project_path.is_dir()
        handler = (project_path / "src/agent/handler.py").read_text()
        assert "AgentDefinition" in handler
        assert config.display_name in handler
