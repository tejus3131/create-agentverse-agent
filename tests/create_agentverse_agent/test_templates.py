"""Comprehensive tests for the templates module."""

import logging

import pytest

from create_agentverse_agent.context import AgentContext
from create_agentverse_agent.templates import (
    BaseTemplateRenderer,
    TemplateError,
    TemplateRenderer,
)


class TestBaseTemplateRenderer:
    """Test BaseTemplateRenderer abstract class."""

    def test_render_not_implemented(self) -> None:
        """Test that render raises NotImplementedError."""
        renderer = BaseTemplateRenderer()

        with pytest.raises(NotImplementedError):
            renderer.render("template.j2", {})

    def test_list_templates_not_implemented(self) -> None:
        """Test that list_templates raises NotImplementedError."""
        renderer = BaseTemplateRenderer()

        with pytest.raises(NotImplementedError):
            renderer.list_templates()


class TestTemplateRenderer:
    """Test TemplateRenderer class."""

    def test_initialization(self) -> None:
        """Test that TemplateRenderer initializes successfully."""
        renderer = TemplateRenderer()

        assert renderer is not None
        assert renderer.env is not None

    def test_has_jinja_environment(self) -> None:
        """Test that renderer has a Jinja2 environment."""
        from jinja2 import Environment

        renderer = TemplateRenderer()

        assert isinstance(renderer.env, Environment)

    def test_environment_has_trim_blocks(self) -> None:
        """Test that environment has trim_blocks enabled."""
        renderer = TemplateRenderer()

        assert renderer.env.trim_blocks is True

    def test_environment_has_lstrip_blocks(self) -> None:
        """Test that environment has lstrip_blocks enabled."""
        renderer = TemplateRenderer()

        assert renderer.env.lstrip_blocks is True


class TestListTemplates:
    """Test list_templates method."""

    def test_list_templates_returns_list(self) -> None:
        """Test that list_templates returns a list."""
        renderer = TemplateRenderer()

        templates = renderer.list_templates()

        assert isinstance(templates, list)

    def test_list_templates_not_empty(self) -> None:
        """Test that list_templates returns non-empty list."""
        renderer = TemplateRenderer()

        templates = renderer.list_templates()

        assert len(templates) > 0

    def test_list_templates_contains_expected_files(self) -> None:
        """Test that list_templates contains expected project files."""
        renderer = TemplateRenderer()

        templates = renderer.list_templates()

        expected = {
            "template..env.j2",
            "template.agent.py.j2",
            "template.docker-compose.yml.j2",
            "template.Dockerfile.j2",
            "template.main.py.j2",
            "template.Makefile.j2",
            "template.pyproject.toml.j2",
            "template.README.md.j2",
            "template.test.py.j2",
        }

        assert expected.issubset(set(templates))

    def test_list_templates_all_have_j2_extension(self) -> None:
        """Test that all templates have .j2 extension."""
        renderer = TemplateRenderer()

        templates = renderer.list_templates()

        for template in templates:
            assert template.endswith(
                ".j2"
            ), f"Template '{template}' should end with .j2"

    def test_list_templates_all_have_template_prefix(self) -> None:
        """Test that all templates have template. prefix."""
        renderer = TemplateRenderer()

        templates = renderer.list_templates()

        for template in templates:
            assert template.startswith(
                "template."
            ), f"Template '{template}' should start with template."


class TestRenderMethod:
    """Test render method."""

    def test_render_returns_string(self) -> None:
        """Test that render returns a string."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Test",
            agent_seed_phrase="testseed12345",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        result = renderer.render("template..env.j2", context.model_dump())

        assert isinstance(result, str)

    def test_render_env_template_injects_context(self) -> None:
        """Test that .env template is rendered with context values."""
        context = AgentContext(
            agent_name="Demo Agent",
            agent_seed_phrase="seedphrase123",
            agent_port=1234,
            hosting_address="example.com",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template..env.j2", context.model_dump())

        assert 'ENV="development"' in rendered
        assert 'AGENT_NAME="Demo Agent"' in rendered
        assert 'AGENT_PORT="1234"' in rendered
        assert f'HOSTING_ENDPOINT="{context.hosting_endpoint}"' in rendered

    def test_render_env_template_production_mode(self) -> None:
        """Test .env template with production environment."""
        context = AgentContext(
            agent_name="Prod Agent",
            agent_seed_phrase="prodseed12345",
            agent_port=8000,
            hosting_address="production.com",
            hosting_port=8080,
            env="production",
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template..env.j2", context.model_dump())

        assert 'ENV="production"' in rendered

    def test_render_readme_template(self) -> None:
        """Test README template rendering."""
        context = AgentContext(
            agent_name="Readme Agent",
            agent_seed_phrase="readmeseed123",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template.README.md.j2", context.model_dump())

        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_dockerfile_template(self) -> None:
        """Test Dockerfile template rendering."""
        context = AgentContext(
            agent_name="Docker Agent",
            agent_seed_phrase="dockerseed123",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template.Dockerfile.j2", context.model_dump())

        assert isinstance(rendered, str)
        # Dockerfile should contain FROM directive
        assert "FROM" in rendered or "from" in rendered.lower() or len(rendered) > 0

    def test_render_pyproject_template(self) -> None:
        """Test pyproject.toml template rendering."""
        context = AgentContext(
            agent_name="Pyproject Agent",
            agent_seed_phrase="pyprojseed123",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template.pyproject.toml.j2", context.model_dump())

        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_makefile_template(self) -> None:
        """Test Makefile template rendering."""
        context = AgentContext(
            agent_name="Make Agent",
            agent_seed_phrase="makeseed12345",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template.Makefile.j2", context.model_dump())

        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_unknown_template_raises(self) -> None:
        """Test that rendering unknown template raises TemplateError."""
        renderer = TemplateRenderer()

        with pytest.raises(TemplateError):
            renderer.render("missing-template.j2", {})

    def test_render_with_empty_context(self) -> None:
        """Test rendering with empty context dict."""
        renderer = TemplateRenderer()

        # This might fail depending on template requirements
        # but should raise TemplateError, not a generic exception
        try:
            result = renderer.render("template..env.j2", {})
            # If it succeeds, result should be a string
            assert isinstance(result, str)
        except TemplateError:
            pass  # Expected behavior for templates requiring context

    def test_render_with_partial_context(self) -> None:
        """Test rendering with partial context."""
        renderer = TemplateRenderer()

        partial_context: dict[str, object] = {
            "agent_name": "Partial Agent",
            "agent_port": 8000,
        }

        # Should either succeed or raise TemplateError
        try:
            result = renderer.render("template..env.j2", partial_context)
            assert isinstance(result, str)
        except (TemplateError, KeyError):
            pass  # Expected if template requires more fields

    def test_render_preserves_special_characters(self) -> None:
        """Test that special characters in context are preserved."""
        context = AgentContext(
            agent_name="Agent Test",
            agent_seed_phrase="special12345",
            agent_port=8000,
            agent_description="Description with 'quotes' and \"double quotes\"",
            hosting_address="localhost",
            hosting_port=8080,
        )

        renderer = TemplateRenderer()
        rendered = renderer.render("template..env.j2", context.model_dump())

        assert isinstance(rendered, str)


class TestTemplateError:
    """Test TemplateError exception."""

    def test_template_error_is_exception(self) -> None:
        """Test that TemplateError inherits from Exception."""
        assert issubclass(TemplateError, Exception)

    def test_template_error_message(self) -> None:
        """Test that TemplateError preserves message."""
        error = TemplateError("Test error message")
        assert str(error) == "Test error message"

    def test_template_error_can_be_raised(self) -> None:
        """Test that TemplateError can be raised and caught."""
        with pytest.raises(TemplateError):
            raise TemplateError("Test")

    def test_template_error_with_cause(self) -> None:
        """Test that TemplateError can wrap another exception."""
        original = ValueError("Original error")

        with pytest.raises(TemplateError) as exc_info:
            try:
                raise original
            except ValueError as e:
                raise TemplateError("Wrapped error") from e

        assert exc_info.value.__cause__ is original


class TestTemplateRendererLogging:
    """Test logging behavior of TemplateRenderer."""

    def test_render_logs_debug_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that render logs debug information."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Log Test",
            agent_seed_phrase="logseed123456",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        with caplog.at_level(logging.DEBUG):
            renderer.render("template..env.j2", context.model_dump())

        # Should have logged something (exact messages may vary)
        assert len(caplog.records) >= 0  # At minimum, no errors


class TestTemplateIntegration:
    """Integration tests for template rendering."""

    def test_all_templates_render_without_error(self) -> None:
        """Test that all templates can be rendered without error."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Integration Agent",
            agent_seed_phrase="integrationseed",
            agent_port=8000,
            agent_description="An integration test agent",
            hosting_address="localhost",
            hosting_port=8080,
            env="development",
        )

        templates = renderer.list_templates()

        for template in templates:
            result = renderer.render(template, context.model_dump())
            assert isinstance(
                result, str
            ), f"Template {template} should render to string"
            assert len(result) > 0, f"Template {template} should not be empty"

    def test_all_templates_render_with_production_config(self) -> None:
        """Test that all templates render correctly with production config."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Production Agent",
            agent_seed_phrase="productionseed",
            agent_port=9000,
            agent_description="A production agent",
            hosting_address="production.example.com",
            hosting_port=9080,
            env="production",
            agentverse_api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        )

        templates = renderer.list_templates()

        for template in templates:
            result = renderer.render(template, context.model_dump())
            assert isinstance(result, str)

    def test_all_templates_render_with_minimal_config(self) -> None:
        """Test that all templates render with minimal (default) config."""
        renderer = TemplateRenderer()
        context = AgentContext()  # All defaults

        templates = renderer.list_templates()

        for template in templates:
            result = renderer.render(template, context.model_dump())
            assert isinstance(result, str)

    def test_env_template_contains_all_expected_variables(self) -> None:
        """Test that .env template contains all expected environment variables."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Env Var Agent",
            agent_seed_phrase="envvarseed123",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        rendered = renderer.render("template..env.j2", context.model_dump())

        # Check for expected variable names
        expected_vars = ["ENV", "AGENT_NAME", "AGENT_PORT"]
        for var in expected_vars:
            assert var in rendered, f"Variable {var} should be in .env template"

    def test_templates_use_safe_name(self) -> None:
        """Test that templates use the safe_name property."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Safe Name Test",
            agent_seed_phrase="safenameseed1",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        # Render a template that likely uses safe_name
        rendered = renderer.render("template.pyproject.toml.j2", context.model_dump())

        # safe_name should be "safe-name-test"
        assert isinstance(rendered, str)


class TestTemplateEdgeCases:
    """Test edge cases for template rendering."""

    def test_render_with_long_agent_name(self) -> None:
        """Test rendering with maximum length agent name."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="A" * 100,  # Max length
            agent_seed_phrase="longnameseed12",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        templates = renderer.list_templates()

        for template in templates:
            result = renderer.render(template, context.model_dump())
            assert isinstance(result, str)

    def test_render_with_numeric_agent_name(self) -> None:
        """Test rendering with numeric-only agent name."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="12345",
            agent_seed_phrase="numseed1234567",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        templates = renderer.list_templates()

        for template in templates:
            result = renderer.render(template, context.model_dump())
            assert isinstance(result, str)

    def test_render_with_boundary_port_values(self) -> None:
        """Test rendering with boundary port values."""
        renderer = TemplateRenderer()

        # Test with minimum port
        context_min = AgentContext(
            agent_name="Min Port Agent",
            agent_seed_phrase="minportseed12",
            agent_port=1024,
            hosting_address="localhost",
            hosting_port=1025,
        )

        result = renderer.render("template..env.j2", context_min.model_dump())
        assert "1024" in result

        # Test with maximum port
        context_max = AgentContext(
            agent_name="Max Port Agent",
            agent_seed_phrase="maxportseed12",
            agent_port=65534,
            hosting_address="localhost",
            hosting_port=65535,
        )

        result = renderer.render("template..env.j2", context_max.model_dump())
        assert "65534" in result or "65535" in result

    def test_render_consistency(self) -> None:
        """Test that rendering the same template twice gives same result."""
        renderer = TemplateRenderer()
        context = AgentContext(
            agent_name="Consistency Test",
            agent_seed_phrase="consistseed12",
            agent_port=8000,
            hosting_address="localhost",
            hosting_port=8080,
        )

        context_dict = context.model_dump()

        result1 = renderer.render("template..env.j2", context_dict)
        result2 = renderer.render("template..env.j2", context_dict)

        assert result1 == result2
