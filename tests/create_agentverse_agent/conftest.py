"""Shared fixtures for scaffold integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from create_agentverse_agent.scaffold import Scaffolder
from create_agentverse_agent.templates import TemplateRenderer


@pytest.fixture
def scaffolder() -> Scaffolder:
    return Scaffolder(TemplateRenderer())


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def uv_available() -> bool:
    return shutil.which("uv") is not None


@pytest.fixture
def docker_available() -> bool:
    return shutil.which("docker") is not None
