"""Helpers for integration tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from create_agentverse_agent.bundle_paths import STATIC_FILES, TEMPLATE_MANIFEST
from create_agentverse_agent.context import (
    EnvSecrets,
    PaymentMethodState,
    ProjectContext,
    default_yml_config,
)
from create_agentverse_agent.scaffold import Scaffolder


def docker_usable() -> bool:
    """True when docker CLI exists and daemon is reachable."""
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def make_context(
    *,
    handle: str,
    name: str | None = None,
    description: str = "Integration test agent",
    port: int = 8000,
    network: str = "testnet",
    project_name: str | None = None,
    stripe: PaymentMethodState = PaymentMethodState.DISABLED,
    skyfire: PaymentMethodState = PaymentMethodState.DISABLED,
    fet: PaymentMethodState = PaymentMethodState.ENABLED,
    agentverse_api_key: str | None = None,
) -> ProjectContext:
    """Build a ProjectContext for integration scenarios."""
    yml = default_yml_config(
        name=name or f"Agent {handle}",
        handle=handle,
        description=description,
        port=port,
        network=network,  # type: ignore[arg-type]
    )
    yml.protocols.payment.methods.fet = fet
    yml.protocols.payment.methods.stripe = stripe
    yml.protocols.payment.methods.skyfire = skyfire

    secrets = EnvSecrets(
        agent_port=port,
        agentverse_api_key=agentverse_api_key,
        agent_seed="a" * 64,
        postgres_password="test-password-123",
    )
    if stripe is PaymentMethodState.ENABLED:
        secrets.stripe_secret_key = "sk_test_integration"
        secrets.stripe_publishable_key = "pk_test_integration"
    if skyfire is PaymentMethodState.ENABLED:
        secrets.skyfire_api_key = "skyfire-key-integration"
        secrets.skyfire_seller_account_id = "seller-integration"
        secrets.skyfire_service_id = "service-integration"

    return ProjectContext(
        project_name=project_name or handle,
        yml=yml,
        secrets=secrets,
    )


def expected_project_files() -> set[str]:
    """All files that a full scaffold should produce."""
    files = {out for _, out in STATIC_FILES}
    files.update(out for _, out in TEMPLATE_MANIFEST)
    files.add("agent.yml")
    return files


def scaffold_project(
    scaffolder: Scaffolder,
    config: ProjectContext,
    *,
    overwrite: bool = False,
) -> Path:
    return scaffolder.create_project(config, overwrite=overwrite)


def run_uv_sync(project_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "sync"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )


def run_in_project(
    project_path: Path,
    code: str,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", "-c", code],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
