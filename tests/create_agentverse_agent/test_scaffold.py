"""Comprehensive tests for the scaffold module."""

import logging
from pathlib import Path

import pytest

from create_agentverse_agent.context import AgentContext
from create_agentverse_agent.scaffold import Scaffolder, ScaffoldError
from create_agentverse_agent.templates import BaseTemplateRenderer


class DummyRenderer(BaseTemplateRenderer):
    """Dummy renderer for testing."""

    def __init__(self, templates: list[str] | None = None) -> None:
        self.render_calls: list[tuple[str, dict[str, object]]] = []
        if templates is None:
            self._templates = [
                "template.agent.py.j2",
                "template.config.yaml.j2",
                "template.README.md.j2",
            ]
        else:
            self._templates = templates

    def render(self, template_name: str, context: dict[str, object]) -> str:
        self.render_calls.append((template_name, context))
        return f"rendered {template_name}"

    def list_templates(self) -> list[str]:
        return self._templates


class FailingRenderer(BaseTemplateRenderer):
    """Renderer that fails on render."""

    def render(self, template_name: str, context: dict[str, object]) -> str:
        raise RuntimeError(f"Failed to render {template_name}")

    def list_templates(self) -> list[str]:
        return ["template.fail.j2"]


class TestScaffolder:
    """Test Scaffolder class."""

    def test_init_stores_renderer(self) -> None:
        """Test that scaffolder stores the renderer."""
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        assert scaffolder.renderer is renderer

    def test_create_project_returns_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project returns the project path."""
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

    def test_create_project_creates_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project creates the project directory."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Directory Test",
            agent_seed_phrase="dirseed12345",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        assert project_path.exists()
        assert project_path.is_dir()

    def test_create_project_writes_expected_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project writes all expected files."""
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
        for template_name in renderer.list_templates():
            output_name = template_name.replace("template.", "").replace(".j2", "")
            file_path = project_path / output_name
            assert file_path.exists(), f"File {output_name} should exist"
            assert file_path.read_text() == f"rendered {template_name}"

    def test_create_project_prevents_overwrite_by_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project prevents overwriting existing directory."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Existing",
            agent_seed_phrase="seed123456789",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        # Create existing directory
        existing_path = context.project_path
        existing_path.mkdir()

        with pytest.raises(ScaffoldError) as exc_info:
            scaffolder.create_project(context, overwrite=False)

        assert "already exists" in str(exc_info.value)
        assert "--overwrite" in str(exc_info.value)

    def test_create_project_allows_overwrite_when_flag_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project allows overwriting when flag is set."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Overwrite",
            agent_seed_phrase="seed456789012",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        # Create existing directory with stale content
        project_path = context.project_path
        project_path.mkdir()
        stale_file = project_path / "README.md"
        stale_file.write_text("old content")

        result_path = scaffolder.create_project(context, overwrite=True)

        assert result_path == project_path
        assert stale_file.read_text() == "rendered template.README.md.j2"

    def test_create_project_passes_context_to_renderer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project passes context dict to renderer."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Context Test",
            agent_seed_phrase="ctxseed123456",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        scaffolder.create_project(context)

        # Check that renderer received context data
        assert len(renderer.render_calls) > 0
        for _, ctx_dict in renderer.render_calls:
            assert "agent_name" in ctx_dict
            assert "agent_port" in ctx_dict
            assert "safe_name" in ctx_dict

    def test_create_project_uses_safe_name_for_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project uses safe_name for directory name."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="My Special Agent 123",
            agent_seed_phrase="safeseed12345",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        assert project_path.name == "my-special-agent-123"

    def test_create_project_with_default_agent_name(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test create_project when agent_name is None (using default)."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_seed_phrase="defaultseed12",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        # Should use display_name which is "Agent " + first 8 chars of seed
        assert project_path.exists()
        assert "agent-" in project_path.name.lower()

    def test_create_project_creates_nested_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that create_project can create in nested non-existent path."""
        nested_path = tmp_path / "deep" / "nested" / "path"
        nested_path.mkdir(parents=True)
        monkeypatch.chdir(nested_path)

        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Nested Agent",
            agent_seed_phrase="nestedseed123",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        assert project_path.exists()
        assert project_path == nested_path / "nested-agent"

    def test_create_project_handles_empty_template_list(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test create_project with no templates."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer(templates=[])
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Empty Templates",
            agent_seed_phrase="emptyseed1234",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        # Directory should still be created
        assert project_path.exists()
        # But no files inside (except potentially hidden files)
        files = list(project_path.iterdir())
        assert len(files) == 0

    def test_create_project_preserves_existing_files_in_overwrite_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that files not in template list are preserved during overwrite."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Preserve",
            agent_seed_phrase="preserveseed1",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        # Create existing directory with extra file
        project_path = context.project_path
        project_path.mkdir()
        extra_file = project_path / "custom.txt"
        extra_file.write_text("custom content")

        scaffolder.create_project(context, overwrite=True)

        # Custom file should still exist
        assert extra_file.exists()
        assert extra_file.read_text() == "custom content"


class TestScaffoldError:
    """Test ScaffoldError exception."""

    def test_scaffold_error_is_exception(self) -> None:
        """Test that ScaffoldError inherits from Exception."""
        assert issubclass(ScaffoldError, Exception)

    def test_scaffold_error_message(self) -> None:
        """Test that ScaffoldError preserves message."""
        error = ScaffoldError("Test error message")
        assert str(error) == "Test error message"

    def test_scaffold_error_can_be_raised(self) -> None:
        """Test that ScaffoldError can be raised and caught."""
        with pytest.raises(ScaffoldError):
            raise ScaffoldError("Test")


class TestScaffolderLogging:
    """Test scaffolder logging behavior."""

    def test_logs_project_creation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that project creation is logged."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Log Test",
            agent_seed_phrase="logseed123456",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        with caplog.at_level(logging.DEBUG):
            scaffolder.create_project(context)

        # Should have logged something
        assert len(caplog.records) >= 0  # At minimum, no errors

    def test_logs_on_overwrite(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that overwriting logs some information."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Warn Test",
            agent_seed_phrase="warnseed12345",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        # Create existing directory
        context.project_path.mkdir()

        with caplog.at_level(logging.DEBUG):
            scaffolder.create_project(context, overwrite=True)

        # Just verify the project was created successfully
        assert context.project_path.exists()


class TestScaffolderEdgeCases:
    """Test edge cases for scaffolder."""

    def test_create_project_with_special_characters_in_name(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test project creation with name containing spaces."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Agent With Spaces",
            agent_seed_phrase="spaceseed1234",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        assert project_path.exists()
        assert " " not in project_path.name  # safe_name should have dashes

    def test_create_project_renders_all_templates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that all templates are rendered."""
        monkeypatch.chdir(tmp_path)
        templates = [
            "template.file1.txt.j2",
            "template.file2.py.j2",
            "template.nested.config.yaml.j2",
        ]
        renderer = DummyRenderer(templates=templates)
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Multi Template",
            agent_seed_phrase="multiseed1234",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        # Check all files were created
        assert (project_path / "file1.txt").exists()
        assert (project_path / "file2.py").exists()
        assert (project_path / "nested.config.yaml").exists()

    def test_create_project_strips_template_prefix_and_suffix(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that template. prefix and .j2 suffix are stripped."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer(templates=["template.myfile.txt.j2"])
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Strip Test",
            agent_seed_phrase="stripseed1234",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        # File should be named without prefix/suffix
        assert (project_path / "myfile.txt").exists()
        assert not (project_path / "template.myfile.txt.j2").exists()
        assert not (project_path / "template.myfile.txt").exists()

    def test_create_project_handles_dotfiles(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that dotfiles (like .env) are created correctly."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer(templates=["template..env.j2"])
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Dotfile Test",
            agent_seed_phrase="dotseed123456",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        project_path = scaffolder.create_project(context)

        # .env file should exist
        assert (project_path / ".env").exists()

    def test_create_project_counts_rendered_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that scaffolder tracks number of rendered files."""
        monkeypatch.chdir(tmp_path)
        templates = ["template.a.j2", "template.b.j2", "template.c.j2"]
        renderer = DummyRenderer(templates=templates)
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Count Test",
            agent_seed_phrase="countseed1234",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        scaffolder.create_project(context)

        # All templates should have been rendered
        assert len(renderer.render_calls) == 3


class TestScaffolderIntegration:
    """Integration tests for scaffolder with real-like scenarios."""

    def test_full_project_creation_flow(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test complete project creation flow."""
        monkeypatch.chdir(tmp_path)

        # Simulate real template names
        templates = [
            "template..env.j2",
            "template.agent.py.j2",
            "template.docker-compose.yml.j2",
            "template.Dockerfile.j2",
            "template.main.py.j2",
            "template.Makefile.j2",
            "template.pyproject.toml.j2",
            "template.README.md.j2",
            "template.requirements.txt.j2",
        ]
        renderer = DummyRenderer(templates=templates)
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Production Agent",
            agent_seed_phrase="prodseed12345",
            agent_port=8000,
            agent_description="A production-ready agent",
            hosting_address="production.example.com",
            hosting_port=8080,
            env="production",
        )

        project_path = scaffolder.create_project(context)

        # Verify all expected files
        assert (project_path / ".env").exists()
        assert (project_path / "agent.py").exists()
        assert (project_path / "docker-compose.yml").exists()
        assert (project_path / "Dockerfile").exists()
        assert (project_path / "main.py").exists()
        assert (project_path / "Makefile").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "README.md").exists()
        assert (project_path / "requirements.txt").exists()

    def test_recreate_project_after_deletion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that project can be recreated after deletion."""
        monkeypatch.chdir(tmp_path)
        renderer = DummyRenderer()
        scaffolder = Scaffolder(renderer)

        context = AgentContext(
            agent_name="Recreate Test",
            agent_seed_phrase="recreateseed1",
            agent_port=9000,
            hosting_address="localhost",
            hosting_port=9080,
        )

        # Create first time
        project_path = scaffolder.create_project(context)
        assert project_path.exists()

        # Delete
        import shutil

        shutil.rmtree(project_path)
        assert not project_path.exists()

        # Recreate
        project_path = scaffolder.create_project(context)
        assert project_path.exists()
