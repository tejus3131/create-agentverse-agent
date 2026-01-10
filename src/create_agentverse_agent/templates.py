# src/create_agentverse_agent/templates.py
import logging
from importlib.resources import files

from jinja2 import Environment, PackageLoader, select_autoescape

logger = logging.getLogger(__name__)


class TemplateError(Exception):
    """Custom exception for template rendering errors."""

    pass


class BaseTemplateRenderer:
    """Base class for template rendering."""

    def render(self, template_name: str, context: dict[str, object]) -> str:
        raise NotImplementedError

    def list_templates(self) -> list[str]:
        raise NotImplementedError


class TemplateRenderer(BaseTemplateRenderer):
    """Handles template loading and rendering."""

    def __init__(self) -> None:
        templates_path = files("create_agentverse_agent").joinpath("templates")
        logger.debug("Initializing TemplateRenderer with path: %s", templates_path)

        self.env = Environment(
            loader=PackageLoader(
                "create_agentverse_agent.templates", str(templates_path)
            ),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.info("TemplateRenderer initialized successfully")

    def render(self, template_name: str, context: dict[str, object]) -> str:
        """Render a single template with context.

        Args:
            template_name: e.g., "template.agent.py.j2"
            context: Dictionary of variables

        Returns:
            Rendered string
        """
        logger.debug(
            "Rendering template: %s with context keys: %s",
            template_name,
            list(context.keys()),
        )
        try:
            template = self.env.get_template(template_name)
            result: str = template.render(**context)
            logger.debug("Successfully rendered template: %s", template_name)
            return result
        except Exception as err:
            logger.exception("Failed to render template: %s", template_name)
            raise TemplateError(f"Error rendering template '{template_name}'") from err

    def list_templates(self) -> list[str]:
        """List all available templates."""
        templates: list[str] = self.env.list_templates()
        logger.debug("Found %d templates: %s", len(templates), templates)
        return templates
