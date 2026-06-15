import logging
import shutil
import subprocess
from pathlib import Path

import yaml

from .bundle_paths import STATIC_DIRECTORIES, STATIC_FILES, bundle_path
from .context import AgentYmlConfig, ProjectContext
from .templates import BaseTemplateRenderer

logger = logging.getLogger(__name__)


class ScaffoldError(Exception):
    """Custom exception for scaffold failures."""


def copy_static_tree(source: Path, destination: Path) -> None:
    """Copy a directory tree from source to destination."""
    if not source.is_dir():
        msg = f"Static bundle directory not found: {source}"
        raise ScaffoldError(msg)
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            if target.exists():
                copy_static_tree(item, target)
            else:
                shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def copy_static_file(source: Path, destination: Path) -> None:
    """Copy a single file, creating parent directories as needed."""
    if not source.is_file():
        msg = f"Static bundle file not found: {source}"
        raise ScaffoldError(msg)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_agent_yml(project_path: Path, config: AgentYmlConfig) -> None:
    """Write agent.yml from validated configuration."""
    output_path = project_path / "agent.yml"
    data = config.model_dump(mode="json")
    content = yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    output_path.write_text(content, encoding="utf-8")


def run_uv_lock(project_path: Path) -> bool:
    """Run uv lock in the generated project if uv is available."""
    uv = shutil.which("uv")
    if uv is None:
        logger.warning("uv not found on PATH — skipping uv lock")
        return False
    try:
        subprocess.run(
            [uv, "lock"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("uv lock completed in %s", project_path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("uv lock failed: %s", exc.stderr or exc)
        return False


class Scaffolder:
    """Handles filesystem operations for project creation."""

    def __init__(self, renderer: BaseTemplateRenderer) -> None:
        self.renderer = renderer

    def create_project(self, context: ProjectContext, overwrite: bool = False) -> Path:
        """Create project directory and write all files."""
        project_path = context.project_path
        logger.info("Creating project at %s", project_path)

        if project_path.exists() and not overwrite:
            logger.error("Directory already exists: %s", project_path)
            raise ScaffoldError(
                f"Directory '{project_path}' already exists. "
                "Use --overwrite to replace it."
            )

        if project_path.exists() and overwrite:
            logger.warning("Overwriting existing directory: %s", project_path)

        project_path.mkdir(parents=True, exist_ok=overwrite)

        for bundle_rel, output_rel in STATIC_DIRECTORIES:
            copy_static_tree(
                bundle_path(bundle_rel),
                project_path / output_rel,
            )

        for bundle_rel, output_rel in STATIC_FILES:
            copy_static_file(
                bundle_path(bundle_rel),
                project_path / output_rel,
            )

        write_agent_yml(project_path, context.yml)

        context_dict = context.model_dump()
        rendered_files = 0
        for template_name, output_rel in self.renderer.template_manifest():
            logger.debug("Rendering template: %s -> %s", template_name, output_rel)
            content = self.renderer.render(template_name, context_dict)
            output_path = project_path / output_rel
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            rendered_files += 1

        lock_ran = run_uv_lock(project_path)
        if not lock_ran:
            logger.debug("Using bundled uv.lock reference file")

        logger.info(
            "Successfully created project with %d rendered templates",
            rendered_files,
        )
        return project_path
