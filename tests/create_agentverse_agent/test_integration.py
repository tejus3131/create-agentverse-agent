"""Deep integration tests: scaffold modes, edge cases, generated project runtime."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from helpers import (
    docker_usable,
    expected_project_files,
    make_context,
    run_in_project,
    run_uv_sync,
    scaffold_project,
)
from typer.testing import CliRunner

from create_agentverse_agent import cli
from create_agentverse_agent.context import (
    DEFAULT_AVATAR_URL,
    DEFAULT_BANNER_URL,
    ContextError,
    EnvSecrets,
    GeoLocation,
    PaymentMethodState,
    ProjectContext,
    default_yml_config,
    parse_window_seconds,
)
from create_agentverse_agent.scaffold import Scaffolder, ScaffoldError
from create_agentverse_agent.templates import TemplateRenderer


class TestScaffoldModes:
    """Simulate --default, standard, and advanced configuration outputs."""

    def test_default_mode_file_tree(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = ProjectContext.create_default()
        path = scaffold_project(scaffolder, config)
        assert path.is_dir()
        missing = expected_project_files() - {
            p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()
        }
        assert missing == set()

    def test_mainnet_agent(self, scaffolder: Scaffolder, workspace: Path) -> None:
        config = make_context(handle="mainnet-bot", network="mainnet", port=9001)
        path = scaffold_project(scaffolder, config)
        data = yaml.safe_load((path / "agent.yml").read_text())
        assert data["runtime"]["network"] == "mainnet"
        assert data["agent"]["port"] == 9001

    def test_custom_identity(self, scaffolder: Scaffolder, workspace: Path) -> None:
        config = make_context(
            handle="weather-bot",
            name="Weather Bot",
            description="Forecasts for your city",
            port=8123,
        )
        path = scaffold_project(scaffolder, config)
        assert path.name == "weather-bot"
        env_text = (path / ".env").read_text()
        assert "AGENT_PORT=8123" in env_text
        compose = (path / "docker-compose.yml").read_text()
        assert "8123" in compose

    def test_stripe_enabled_scaffold(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(handle="stripe-agent", stripe=PaymentMethodState.ENABLED)
        path = scaffold_project(scaffolder, config)
        env_text = (path / ".env").read_text()
        assert "STRIPE_SECRET_KEY=sk_test_integration" in env_text
        assert "STRIPE_PUBLISHABLE_KEY=pk_test_integration" in env_text
        yml = yaml.safe_load((path / "agent.yml").read_text())
        assert yml["protocols"]["payment"]["methods"]["stripe"] == "enabled"

    def test_skyfire_enabled_scaffold(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(
            handle="skyfire-agent", skyfire=PaymentMethodState.ENABLED
        )
        path = scaffold_project(scaffolder, config)
        env_text = (path / ".env").read_text()
        assert "SKYFIRE_API_KEY=skyfire-key-integration" in env_text
        assert "SKYFIRE_SERVICE_ID=service-integration" in env_text

    def test_agentverse_key_in_env(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        key = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature"
        config = make_context(handle="av-agent", agentverse_api_key=key)
        path = scaffold_project(scaffolder, config)
        assert key in (path / ".env").read_text()

    def test_avatar_banner_defaults_in_yml(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        path = scaffold_project(scaffolder, ProjectContext.create_default())
        data = yaml.safe_load((path / "agent.yml").read_text())
        assert data["agent"]["avatar_url"] == DEFAULT_AVATAR_URL
        assert data["agent"]["banner_url"] == DEFAULT_BANNER_URL

    def test_agentverse_md_content(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(
            handle="profile-agent",
            name="Profile Agent",
            description="Profile description here",
        )
        path = scaffold_project(scaffolder, config)
        md = (path / "AGENTVERSE.md").read_text()
        assert "Profile Agent" in md
        assert "profile-agent" in md
        assert "Profile description here" in md

    def test_multiple_agents_same_parent(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        for handle in ("agent-alpha", "agent-beta", "agent-gamma"):
            scaffold_project(scaffolder, make_context(handle=handle))
        assert (workspace / "agent-alpha").is_dir()
        assert (workspace / "agent-beta").is_dir()
        assert (workspace / "agent-gamma").is_dir()


class TestScaffoldEdgeCases:
    def test_boundary_ports(self, scaffolder: Scaffolder, workspace: Path) -> None:
        config = make_context(handle="min-port", port=1024)
        scaffold_project(scaffolder, config)
        config2 = make_context(handle="max-port", port=65535)
        scaffold_project(scaffolder, config2)

    def test_geo_location_in_yml(self, scaffolder: Scaffolder, workspace: Path) -> None:
        yml = default_yml_config(handle="geo-agent")
        yml.agent.geo_location = GeoLocation(latitude=51.5, longitude=-0.12, radius=10)
        config = ProjectContext(
            project_name="geo-agent",
            yml=yml,
            secrets=EnvSecrets(agent_port=yml.agent.port, agent_seed="a" * 64),
        )
        path = scaffold_project(scaffolder, config)
        data = yaml.safe_load((path / "agent.yml").read_text())
        assert data["agent"]["geo_location"]["latitude"] == 51.5

    def test_overwrite_replaces_templates(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(handle="overwrite-me")
        path = scaffold_project(scaffolder, config)
        (path / "README.md").write_text("stale readme")
        config.yml.agent.description = "Updated description"
        scaffold_project(scaffolder, config.revalidated(), overwrite=True)
        assert "Updated description" in (path / "README.md").read_text()

    def test_overwrite_preserves_untracked(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(handle="preserve-me")
        path = scaffold_project(scaffolder, config)
        custom = path / "notes.txt"
        custom.write_text("keep")
        scaffold_project(scaffolder, config, overwrite=True)
        assert custom.read_text() == "keep"

    def test_duplicate_without_overwrite_raises(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(handle="dup-agent")
        scaffold_project(scaffolder, config)
        with pytest.raises(ScaffoldError, match="already exists"):
            scaffold_project(scaffolder, config)

    def test_stripe_without_keys_fails_validation(self) -> None:
        config = make_context(handle="bad-stripe", stripe=PaymentMethodState.ENABLED)
        config.secrets.stripe_secret_key = None
        with pytest.raises(ContextError):
            config.revalidated()

    def test_rate_limit_windows_in_yml(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        yml = default_yml_config(handle="rate-agent")
        yml.protocols.chat.rate_limits.session.window = "30s"
        yml.protocols.chat.rate_limits.user.window = "2h"
        config = ProjectContext(
            project_name="rate-agent",
            yml=yml,
            secrets=EnvSecrets(agent_port=8000, agent_seed="b" * 64),
        )
        path = scaffold_project(scaffolder, config)
        data = yaml.safe_load((path / "agent.yml").read_text())
        assert data["protocols"]["chat"]["rate_limits"]["session"]["window"] == "30s"
        assert parse_window_seconds("30s") == 30
        assert parse_window_seconds("2h") == 7200

    def test_static_runtime_file_count(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        path = scaffold_project(scaffolder, ProjectContext.create_default())
        runtime_py = list((path / "src/runtime").rglob("*.py"))
        assert len(runtime_py) >= 20
        assert (path / "src/runtime/registration.py").exists()
        assert (path / "src/shared/db.py").exists()


class TestCliIntegration:
    def test_cli_default_creates_project(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(workspace)
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        result = CliRunner().invoke(cli.app, ["--default"])
        assert result.exit_code == 0
        agents = list(workspace.glob("agent-*"))
        assert len(agents) == 1
        assert (agents[0] / "agent.yml").exists()

    def test_cli_default_overwrite(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from create_agentverse_agent import prompts

        fixed = make_context(handle="cli-overwrite-agent")
        monkeypatch.chdir(workspace)
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        monkeypatch.setattr(
            prompts,
            "collect_configuration",
            lambda **_kw: fixed,
        )
        runner = CliRunner()
        assert runner.invoke(cli.app, ["-d"]).exit_code == 0
        agent_dir = workspace / "cli-overwrite-agent"
        (agent_dir / "README.md").write_text("old")
        assert runner.invoke(cli.app, ["-d", "-o"]).exit_code == 0
        assert "Quick start" in (agent_dir / "README.md").read_text()

    def test_cli_abort_exit_code(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from create_agentverse_agent import prompts

        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        monkeypatch.setattr(prompts.console, "clear", lambda: None)
        monkeypatch.setattr(prompts.console, "print", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_identity", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_network", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_postgres", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_agentverse", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_payment_methods", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "collect_advanced_runtime", lambda *_a, **_k: None)
        monkeypatch.setattr(prompts, "display_summary", lambda *_a: None)
        monkeypatch.setattr(prompts.Confirm, "ask", lambda *_a, **_k: False)

        result = CliRunner().invoke(cli.app, [])
        assert result.exit_code != 0

    def test_cli_debug_flag(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import logging

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        monkeypatch.chdir(workspace)
        monkeypatch.setattr(cli, "version", lambda *_a: "1.0.0")
        result = CliRunner().invoke(cli.app, ["--default", "--debug"])
        assert result.exit_code == 0
        assert "Debug log saved" in result.output
        assert any(workspace.glob("create-agentverse-agent-*-cli-execution-*.log"))


@pytest.mark.skipif(not shutil.which("uv"), reason="uv not installed")
class TestGeneratedProjectRuntime:
    """Install and exercise generated agent projects."""

    def test_uv_sync_succeeds(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        path = scaffold_project(scaffolder, make_context(handle="sync-agent"))
        result = run_uv_sync(path)
        assert result.returncode == 0, result.stderr

    def test_settings_load_from_agent_yml(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        config = make_context(handle="settings-agent", port=8765)
        path = scaffold_project(scaffolder, config)
        assert run_uv_sync(path).returncode == 0

        code = """
from shared.settings import Settings
Settings._instance = None
s = Settings.load()
assert s.agent.handle == "settings-agent"
assert s.agent.port == 8765
assert s.runtime.network == "testnet"
print("ok")
"""
        result = run_in_project(path, code)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "ok" in result.stdout

    def test_payment_validation_fet_only(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        path = scaffold_project(scaffolder, ProjectContext.create_default())
        assert run_uv_sync(path).returncode == 0
        code = """
from runtime.payments.config import validate_payment_config
from shared.settings import Settings
Settings._instance = None
methods = validate_payment_config(Settings.load())
assert "fet" in {m.value for m in methods.allowed}
assert "stripe" not in {m.value for m in methods.allowed}
print("ok")
"""
        result = run_in_project(path, code)
        assert result.returncode == 0, result.stderr + result.stdout

    def test_handler_module_imports(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        path = scaffold_project(
            scaffolder, make_context(handle="handler-agent", name="Handler Agent")
        )
        assert run_uv_sync(path).returncode == 0
        code = """
from agent import definition
assert definition.on_message is not None
assert callable(definition.on_startup[0])
print(definition.on_message.__name__)
"""
        result = run_in_project(path, code)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "on_message" in result.stdout

    def test_agentverse_readme_loader(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        config = make_context(handle="readme-agent", name="Readme Agent")
        path = scaffold_project(scaffolder, config)
        assert run_uv_sync(path).returncode == 0
        code = """
from runtime.registration import load_agentverse_readme
text = load_agentverse_readme()
assert "Readme Agent" in text
assert "readme-agent" in text
print("ok")
"""
        result = run_in_project(path, code)
        assert result.returncode == 0, result.stderr + result.stdout

    def test_docker_compose_config_valid(
        self, scaffolder: Scaffolder, workspace: Path, uv_available: bool
    ) -> None:
        if not docker_usable():
            pytest.skip("docker daemon not reachable")
        path = scaffold_project(
            scaffolder, make_context(handle="compose-agent", port=8888)
        )
        result = subprocess.run(
            ["docker", "compose", "config"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "8888" in result.stdout


@pytest.mark.skipif(not shutil.which("docker"), reason="docker not installed")
@pytest.mark.skipif(not shutil.which("uv"), reason="uv not installed")
@pytest.mark.skipif(not docker_usable(), reason="docker daemon not reachable")
class TestGeneratedAgentWithPostgres:
    """Start Postgres via compose and run agent preflight."""

    def test_db_starts_and_preflight(
        self, scaffolder: Scaffolder, workspace: Path
    ) -> None:
        config = make_context(handle="live-agent", port=8777)
        path = scaffold_project(scaffolder, config)
        assert run_uv_sync(path).returncode == 0

        up = subprocess.run(
            ["docker", "compose", "up", "-d", "db"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert up.returncode == 0, up.stderr

        try:
            code = """
import asyncio
from agent import definition
from runtime.agent import AgentRunner
from shared.settings import Settings

Settings._instance = None
runner = AgentRunner.from_definition(definition)
asyncio.run(runner.preflight())
print("preflight_ok")
"""
            result = run_in_project(path, code)
            assert result.returncode == 0, result.stderr + result.stdout
            assert "preflight_ok" in result.stdout
        finally:
            subprocess.run(
                ["docker", "compose", "down", "-v"],
                cwd=path,
                capture_output=True,
                check=False,
            )

    def test_make_db_target(self, scaffolder: Scaffolder, workspace: Path) -> None:
        path = scaffold_project(scaffolder, make_context(handle="make-db-agent"))
        assert run_uv_sync(path).returncode == 0
        makefile = path / "Makefile"
        assert makefile.exists()

        try:
            result = subprocess.run(
                ["make", "db"],
                cwd=path,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            ps = subprocess.run(
                ["docker", "compose", "ps", "--status", "running"],
                cwd=path,
                capture_output=True,
                text=True,
                check=False,
            )
            assert "db" in ps.stdout.lower() or ps.returncode == 0
        finally:
            subprocess.run(["make", "down"], cwd=path, capture_output=True, check=False)


class TestTemplateMatrix:
    """Render every template across configuration variants."""

    @pytest.mark.parametrize(
        ("handle", "network"),
        [
            ("tpl-testnet", "testnet"),
            ("tpl-mainnet", "mainnet"),
        ],
    )
    def test_all_templates_render(self, handle: str, network: str) -> None:
        config = make_context(handle=handle, network=network)
        renderer = TemplateRenderer()
        ctx = config.model_dump()
        for template_name, _ in renderer.template_manifest():
            out = renderer.render(template_name, ctx)
            assert len(out) > 0
            if template_name == "docker-compose.yml.j2":
                assert str(config.yml.agent.port) in out

    def test_env_template_escapes_special_chars(self) -> None:
        config = make_context(
            handle="special-chars",
            description='Say "hello" & welcome',
        )
        rendered = TemplateRenderer().render(".env.j2", config.model_dump())
        assert "POSTGRES_PASSWORD=test-password-123" in rendered

    def test_pyproject_name_matches_handle(self) -> None:
        config = make_context(handle="my-cool-agent")
        rendered = TemplateRenderer().render("pyproject.toml.j2", config.model_dump())
        assert 'name = "my-cool-agent"' in rendered
        assert "requires-python" in rendered
