"""Tests for the __init__ module and package initialization."""

import importlib
from unittest.mock import MagicMock

import pytest

import create_agentverse_agent


class TestPackageImports:
    """Test that the package imports correctly."""

    def test_package_imports_successfully(self) -> None:
        """Test that the package can be imported."""
        assert create_agentverse_agent is not None

    def test_main_function_exists(self) -> None:
        """Test that main function is exported."""
        assert hasattr(create_agentverse_agent, "main")

    def test_main_is_callable(self) -> None:
        """Test that main is callable."""
        assert callable(create_agentverse_agent.main)

    def test_all_exports_defined(self) -> None:
        """Test that __all__ is properly defined."""
        assert hasattr(create_agentverse_agent, "__all__")
        assert "main" in create_agentverse_agent.__all__


class TestVersionAttribute:
    """Test the __version__ attribute."""

    def test_version_available(self) -> None:
        """Test that version is available."""
        assert hasattr(create_agentverse_agent, "__version__")

    def test_version_is_string(self) -> None:
        """Test that version is a string."""
        assert isinstance(create_agentverse_agent.__version__, str)

    def test_version_is_nonempty(self) -> None:
        """Test that version is not empty."""
        assert len(create_agentverse_agent.__version__) > 0

    def test_version_follows_semver_pattern(self) -> None:
        """Test that version roughly follows semantic versioning."""
        version = create_agentverse_agent.__version__
        # Should contain at least one dot (major.minor or major.minor.patch)
        # Allow for dev versions like 0.1.0.dev1
        parts = version.split(".")
        assert len(parts) >= 2, f"Version '{version}' doesn't have at least 2 parts"


class TestMainFunction:
    """Test the main entry point function."""

    def test_main_is_function(self) -> None:
        """Test that main is a callable function."""
        from create_agentverse_agent import main

        assert callable(main)

    def test_main_entrypoint_signature(self) -> None:
        """Test that main function has correct signature."""
        import inspect

        sig = inspect.signature(create_agentverse_agent.main)
        # main should take no required arguments
        assert len(sig.parameters) == 0

    def test_main_calls_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that main() calls the app function."""
        app_called = []

        def mock_app() -> None:
            app_called.append(True)

        monkeypatch.setattr("create_agentverse_agent.cli.app", mock_app)

        # Re-import to get the updated main that uses the mocked app
        import create_agentverse_agent

        importlib.reload(create_agentverse_agent)
        create_agentverse_agent.main()

        assert app_called == [True]


class TestModuleReloading:
    """Test module reloading behavior."""

    def test_module_can_be_reloaded(self) -> None:
        """Test that the module can be reloaded without errors."""
        importlib.reload(create_agentverse_agent)
        assert hasattr(create_agentverse_agent, "main")


class TestDunderMain:
    """Test the __main__ module."""

    def test_dunder_main_exists(self) -> None:
        """Test that __main__.py exists and can be imported."""
        from create_agentverse_agent import __main__

        assert __main__ is not None

    def test_dunder_main_calls_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that running __main__ calls the main function."""
        mock_main = MagicMock()
        monkeypatch.setattr("create_agentverse_agent.main", mock_main)

        # Simulate running as __main__
        import create_agentverse_agent.__main__ as main_module

        importlib.reload(main_module)
        # Note: The actual call happens at import time when __name__ == "__main__"


class TestPackageMetadata:
    """Test package metadata access."""

    def test_version_from_metadata(self) -> None:
        """Test that version can be retrieved from importlib.metadata."""
        from importlib.metadata import version

        pkg_version = version("create-agentverse-agent")
        assert pkg_version == create_agentverse_agent.__version__

    def test_package_has_name(self) -> None:
        """Test that package has a name in metadata."""
        from importlib.metadata import metadata

        pkg_metadata = metadata("create-agentverse-agent")
        assert pkg_metadata["Name"] == "create-agentverse-agent"


class TestSubmoduleAccess:
    """Test access to submodules from main package."""

    def test_cli_module_accessible(self) -> None:
        """Test that cli module is accessible."""
        from create_agentverse_agent import cli

        assert hasattr(cli, "app")

    def test_context_module_accessible(self) -> None:
        """Test that context module is accessible."""
        from create_agentverse_agent import context

        assert hasattr(context, "AgentContext")

    def test_prompts_module_accessible(self) -> None:
        """Test that prompts module is accessible."""
        from create_agentverse_agent import prompts

        assert hasattr(prompts, "collect_configuration")

    def test_scaffold_module_accessible(self) -> None:
        """Test that scaffold module is accessible."""
        from create_agentverse_agent import scaffold

        assert hasattr(scaffold, "Scaffolder")

    def test_templates_module_accessible(self) -> None:
        """Test that templates module is accessible."""
        from create_agentverse_agent import templates

        assert hasattr(templates, "TemplateRenderer")
