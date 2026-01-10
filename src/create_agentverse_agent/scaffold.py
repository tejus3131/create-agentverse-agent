import logging
from pathlib import Path
from typing import ClassVar

from .context import AgentContext
from .templates import BaseTemplateRenderer

logger = logging.getLogger(__name__)


class ScaffoldError(Exception):
    """Custom exception for existing project directory."""

    pass


class Scaffolder:
    """Handles filesystem operations for project creation."""

    # Map template files to output files
    TEMPLATE_MAP: ClassVar[dict[str, str]] = {
        "template.agent.py.j2": "agent.py",
        "template.main.py.j2": "main.py",
        "template.Dockerfile.j2": "Dockerfile",
        "template.docker-compose.yml.j2": "docker-compose.yml",
        "template.pyproject.toml.j2": "pyproject.toml",
        "template.requirements.txt.j2": "requirements.txt",
        "template.env.j2": ".env",
        "template.README.md.j2": "README.md",
    }

    def __init__(self, renderer: BaseTemplateRenderer) -> None:
        self.renderer = renderer

    def create_project(self, context: AgentContext, overwrite: bool = False) -> Path:
        """Create project directory and write all files.

        Args:
            context: Validated agent configuration
            overwrite: Allow overwriting existing directory
        """
        project_path = context.project_path
        logger.info("Creating project at %s", project_path)

        # Safety check
        if project_path.exists() and not overwrite:
            logger.error("Directory already exists: %s", project_path)
            raise ScaffoldError(
                f"Directory '{project_path}' already exists. "
                "Use --overwrite to replace it."
            )

        if project_path.exists() and overwrite:
            logger.warning("Overwriting existing directory: %s", project_path)

        # Create directory
        project_path.mkdir(parents=True, exist_ok=overwrite)
        logger.debug("Created directory: %s", project_path)

        # Write each file
        context_dict = context.model_dump()
        for template_name, output_name in self.TEMPLATE_MAP.items():
            logger.debug("Rendering template: %s -> %s", template_name, output_name)
            content = self.renderer.render(template_name, context_dict)
            output_path = project_path / output_name
            output_path.write_text(content)
            logger.debug("Wrote file: %s", output_path)

        logger.info(
            "Successfully created project with %d files", len(self.TEMPLATE_MAP)
        )
        return project_path
