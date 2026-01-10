from pathlib import Path

import pytest

from create_agentverse_agent.context import AgentContext
from create_agentverse_agent.scaffold import Scaffolder, ScaffoldError
from create_agentverse_agent.templates import BaseTemplateRenderer


class DummyRenderer(BaseTemplateRenderer):
    def __init__(self) -> None:
        self.render_calls: list[tuple[str, dict[str, object]]] = []

    def render(self, template_name: str, context: dict[str, object]) -> str:
        self.render_calls.append((template_name, context))
        return f"rendered {template_name}"


def test_create_project_writes_expected_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    renderer = DummyRenderer()
    scaffolder = Scaffolder(renderer)

    context = AgentContext(
        agent_name="Test Agent",
        agent_seed_phrase="seedphrase123",
        agent_port=9000,
        hosting_address="example.com",
        hosting_port=9080,
    )

    project_path = scaffolder.create_project(context)

    assert project_path == tmp_path / "test-agent"
    for template, output in Scaffolder.TEMPLATE_MAP.items():
        file_path = project_path / output
        assert file_path.exists()
        assert file_path.read_text() == f"rendered {template}"


def test_create_project_prevents_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    renderer = DummyRenderer()
    scaffolder = Scaffolder(renderer)

    context = AgentContext(agent_name="Existing", agent_seed_phrase="seed123")

    existing_path = context.project_path
    existing_path.mkdir()

    with pytest.raises(ScaffoldError):
        scaffolder.create_project(context, overwrite=False)


def test_create_project_allows_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    renderer = DummyRenderer()
    scaffolder = Scaffolder(renderer)

    context = AgentContext(agent_name="Overwrite", agent_seed_phrase="seed456")

    project_path = context.project_path
    project_path.mkdir()
    stale_file = project_path / "README.md"
    stale_file.write_text("old content")

    result_path = scaffolder.create_project(context, overwrite=True)

    assert result_path == project_path
    assert stale_file.read_text() == "rendered template.README.md.j2"
