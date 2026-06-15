"""Tests for the templates module."""

from __future__ import annotations

import pytest

from create_agentverse_agent.context import ProjectContext
from create_agentverse_agent.templates import (
    BaseTemplateRenderer,
    TemplateError,
    TemplateRenderer,
)


class TestBaseTemplateRenderer:
    def test_render_not_implemented(self) -> None:
        renderer = BaseTemplateRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render(".env.j2", {})

    def test_manifest_not_implemented(self) -> None:
        renderer = BaseTemplateRenderer()
        with pytest.raises(NotImplementedError):
            renderer.template_manifest()


class TestTemplateRenderer:
    def test_initialization(self) -> None:
        renderer = TemplateRenderer()
        assert renderer.env is not None

    def test_list_templates_expected(self) -> None:
        renderer = TemplateRenderer()
        templates = set(renderer.list_templates())
        expected = {
            ".env.j2",
            "pyproject.toml.j2",
            "README.md.j2",
            "AGENTVERSE.md.j2",
            "docker-compose.yml.j2",
            "handler.py.j2",
        }
        assert expected.issubset(templates)

    def test_manifest_paths(self) -> None:
        renderer = TemplateRenderer()
        manifest = dict(renderer.template_manifest())
        assert manifest[".env.j2"] == ".env"
        assert manifest["handler.py.j2"] == "src/agent/handler.py"

    def test_render_env_template(self) -> None:
        config = ProjectContext.create_default()
        renderer = TemplateRenderer()
        rendered = renderer.render(".env.j2", config.model_dump())
        assert "POSTGRES_HOST=localhost" in rendered
        assert "AGENT_SEED=" in rendered

    def test_render_pyproject_template(self) -> None:
        config = ProjectContext.create_default()
        renderer = TemplateRenderer()
        rendered = renderer.render("pyproject.toml.j2", config.model_dump())
        assert f'name = "{config.project_name}"' in rendered
        assert "uagents>=" in rendered

    def test_render_handler_template(self) -> None:
        config = ProjectContext.create_default()
        renderer = TemplateRenderer()
        rendered = renderer.render("handler.py.j2", config.model_dump())
        assert "AgentDefinition" in rendered
        assert config.display_name in rendered

    def test_render_agentverse_template(self) -> None:
        config = ProjectContext.create_default()
        renderer = TemplateRenderer()
        rendered = renderer.render("AGENTVERSE.md.j2", config.model_dump())
        assert config.yml.agent.name in rendered
        assert config.yml.agent.handle in rendered
        assert config.yml.agent.description in rendered
        assert "AGENTVERSE_API_KEY" in rendered

    def test_render_unknown_raises(self) -> None:
        renderer = TemplateRenderer()
        with pytest.raises(TemplateError):
            renderer.render("missing.j2", {})

    def test_all_manifest_templates_render(self) -> None:
        config = ProjectContext.create_default()
        renderer = TemplateRenderer()
        for template_name, _output in renderer.template_manifest():
            result = renderer.render(template_name, config.model_dump())
            assert isinstance(result, str)
            assert len(result) > 0
