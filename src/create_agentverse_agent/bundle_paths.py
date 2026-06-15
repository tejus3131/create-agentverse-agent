# src/create_agentverse_agent/bundle_paths.py
"""Paths to packaged static scaffold bundle resources."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

PACKAGE = "create_agentverse_agent"
BUNDLE_ROOT = files(PACKAGE).joinpath("bundle")


def bundle_path(*parts: str) -> Path:
    """Resolve a path inside the packaged bundle directory."""
    return Path(str(BUNDLE_ROOT.joinpath(*parts)))


STATIC_DIRECTORIES: list[tuple[str, str]] = [
    ("src/runtime", "src/runtime"),
    ("src/shared", "src/shared"),
]

STATIC_FILES: list[tuple[str, str]] = [
    ("schema.sql", "schema.sql"),
    ("Dockerfile", "Dockerfile"),
    (".dockerignore", ".dockerignore"),
    ("Makefile", "Makefile"),
    ("docker/init-pod-role.sh", "docker/init-pod-role.sh"),
    ("src/agent/__init__.py", "src/agent/__init__.py"),
    ("uv.lock", "uv.lock"),
    (".env.example", ".env.example"),
]

TEMPLATE_MANIFEST: list[tuple[str, str]] = [
    (".env.j2", ".env"),
    ("pyproject.toml.j2", "pyproject.toml"),
    ("README.md.j2", "README.md"),
    ("AGENTVERSE.md.j2", "AGENTVERSE.md"),
    ("docker-compose.yml.j2", "docker-compose.yml"),
    ("handler.py.j2", "src/agent/handler.py"),
]
