import pytest

from create_agentverse_agent.context import AgentContext
from create_agentverse_agent.templates import TemplateError, TemplateRenderer


def test_list_templates_contains_project_files() -> None:
    renderer = TemplateRenderer()

    templates = renderer.list_templates()

    expected = {
        "template.agent.py.j2",
        "template.main.py.j2",
        "template.Dockerfile.j2",
        "template.docker-compose.yml.j2",
        "template.pyproject.toml.j2",
        "template.requirements.txt.j2",
        "template.env.j2",
        "template.README.md.j2",
    }

    assert expected.issubset(set(templates))


def test_render_env_template_injects_context() -> None:
    context = AgentContext(
        agent_name="Demo Agent",
        agent_seed_phrase="seedphrase123",
        agent_port=1234,
        hosting_address="example.com",
        hosting_port=8080,
    )

    renderer = TemplateRenderer()
    rendered = renderer.render("template.env.j2", context.model_dump())

    assert 'ENV="development"' in rendered
    assert 'AGENT_NAME="Demo Agent"' in rendered
    assert 'AGENT_PORT="1234"' in rendered
    assert f'HOSTING_ENDPOINT="{context.hosting_endpoint}"' in rendered


def test_render_unknown_template_raises() -> None:
    renderer = TemplateRenderer()

    with pytest.raises(TemplateError):
        renderer.render("missing-template.j2", {})
