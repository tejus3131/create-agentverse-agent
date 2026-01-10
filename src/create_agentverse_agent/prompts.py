import logging

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from .context import AgentContext

logger = logging.getLogger(__name__)

console = Console()


def _header(text: str, emoji: str = "✨") -> None:
    """Display a stylish section header."""
    logger.debug(f"Displaying header: {text}")
    console.print()
    console.print(f"[bold cyan]{emoji}  {text}[/bold cyan]")
    console.print(f"[dim blue]   {'─' * (len(text) + 2)}[/dim blue]")


def _success(text: str) -> None:
    """Display a success message."""
    logger.info(text)
    console.print(f"[dim green]   ✓ {text}[/dim green]")


def _hint(text: str) -> None:
    """Display a helpful hint."""
    logger.debug(f"Hint: {text}")
    console.print(f"[dim yellow]   💡 {text}[/dim yellow]")


def _prompt_with_style(
    prompt_text: str,
    default: str | None = None,
    password: bool = False,
) -> str:
    """Styled prompt wrapper."""
    logger.debug(f"Prompting user: {prompt_text}")
    formatted_prompt = f"   [bold white]{prompt_text}[/bold white]"

    if default is not None:
        result = Prompt.ask(
            formatted_prompt,
            default=default,
            password=password,
            console=console,
        )
    else:
        result = Prompt.ask(
            formatted_prompt,
            password=password,
            console=console,
        )
        result = result if result else ""

    if not password:
        logger.debug(f"User input for '{prompt_text}': {result}")
    else:
        logger.debug(f"User input for '{prompt_text}': [REDACTED]")
    return result


def _prompt_int(prompt_text: str, default: int) -> int:
    """Prompt for integer input."""
    logger.debug(f"Prompting for integer: {prompt_text} (default: {default})")
    while True:
        response = _prompt_with_style(prompt_text, default=str(default))
        try:
            value = int(response)
            logger.debug(f"Integer input accepted: {value}")
            return value
        except ValueError:
            logger.warning(f"Invalid integer input: {response}")
            console.print("[red]   Please enter a valid number[/red]")


def _prompt_choice(prompt_text: str, choices: list[str], default: str) -> str:
    """Prompt for choice input."""
    logger.debug(f"Prompting for choice: {prompt_text} (choices: {choices})")
    formatted_choices = " / ".join(f"[cyan]{c}[/cyan]" for c in choices)
    full_prompt = f"   [bold white]{prompt_text}[/bold white] ({formatted_choices})"

    while True:
        response = Prompt.ask(
            full_prompt,
            default=default,
            console=console,
        ).lower()
        if response in [c.lower() for c in choices]:
            logger.debug(f"Choice selected: {response}")
            return response
        logger.warning(f"Invalid choice: {response}")
        console.print(f"[red]   Please choose one of: {', '.join(choices)}[/red]")


def _collect_agent_info(config: AgentContext, skip: bool = False) -> None:
    """Collect basic agent information."""
    logger.info("Collecting agent information" + (" (skipped)" if skip else ""))
    if skip:
        _success("Using default agent configuration")
        return

    _header("Agent Identity", "🤖")

    config.agent_name = _prompt_with_style(
        "What should we call your agent?",
        default=config.display_name,
    )
    logger.info(f"Agent name set to: {config.agent_name}")

    _hint("Your seed phrase is like a password - keep it safe!")
    config.agent_seed_phrase = _prompt_with_style(
        "Agent seed phrase",
        default=config.agent_seed_phrase,
        password=True,
    )
    logger.info("Agent seed phrase configured")

    config.agent_port = _prompt_int(
        "Which port should your agent run on?",
        default=config.agent_port,
    )
    logger.info(f"Agent port set to: {config.agent_port}")

    config.agent_description = _prompt_with_style(
        "Describe your agent in a few words",
        default=config.agent_description,
    )
    logger.info(f"Agent description set to: {config.agent_description}")


def _collect_hosting_info(config: AgentContext, skip: bool = False) -> None:
    """Collect hosting configuration."""
    logger.info("Collecting hosting information" + (" (skipped)" if skip else ""))
    if skip:
        _success("Using default hosting configuration")
        return

    _header("Hosting Setup", "🌐")

    config.hosting_address = _prompt_with_style(
        "Where will your agent be hosted?",
        default=config.hosting_address,
    )
    logger.info(f"Hosting address set to: {config.hosting_address}")

    config.hosting_port = _prompt_int(
        "Hosting port",
        default=config.hosting_port,
    )
    logger.info(f"Hosting port set to: {config.hosting_port}")


def _collect_environment_and_keys(config: AgentContext, skip: bool = False) -> None:
    """Collect environment and API keys."""
    logger.info("Collecting environment and API keys" + (" (skipped)" if skip else ""))
    if skip:
        _success("Skipping API keys (you can add them later)")
        return

    _header("Environment Configuration", "⚙️")

    config.env = _prompt_choice(
        "Which environment are you deploying to?",
        choices=["development", "production"],
        default=config.env,
    )
    logger.info(f"Environment set to: {config.env}")

    console.print()
    _hint("API keys are optional - you can add them to .env later")

    if Confirm.ask(
        "   [bold]🔑 Add AgentVerse API Key now?[/bold]", default=False, console=console
    ):
        config.agentverse_api_key = _prompt_with_style(
            "AgentVerse API Key",
            password=True,
        )
        logger.info("AgentVerse API key configured")
    else:
        logger.debug("AgentVerse API key skipped")


def _display_summary(config: AgentContext) -> None:
    """Display configuration summary using Rich table."""
    logger.debug("Displaying configuration summary")
    console.print()

    # Create summary panel
    summary_text = Text()

    # Agent Info
    summary_text.append("🤖 Agent\n", style="bold cyan")
    summary_text.append("   Name        : ", style="dim")
    summary_text.append(f"{config.display_name}\n", style="bold white")
    summary_text.append("   Port        : ", style="dim")
    summary_text.append(f"{config.agent_port}\n", style="white")
    summary_text.append("   Seed Phrase : ", style="dim")
    summary_text.append(f"{config.agent_seed_phrase[:8]}{'•' * 10}\n", style="yellow")
    summary_text.append("   Description : ", style="dim")
    summary_text.append(f"{config.agent_description}\n\n", style="white")

    # Hosting
    summary_text.append("🌐 Hosting\n", style="bold cyan")
    summary_text.append("   Address : ", style="dim")
    summary_text.append(f"{config.hosting_address}\n", style="white")
    summary_text.append("   Port    : ", style="dim")
    summary_text.append(f"{config.hosting_port}\n\n", style="white")

    # Environment
    summary_text.append("⚙️  Environment\n", style="bold cyan")
    summary_text.append("   Mode : ", style="dim")
    env_style = "bold green" if config.env == "development" else "bold red"
    summary_text.append(f"{config.env}\n", style=env_style)

    summary_text.append("   AgentVerse API Key : ", style="dim")
    if config.agentverse_api_key:
        summary_text.append(f"{config.agentverse_api_key[:8]}•••", style="white")
    else:
        summary_text.append("Not set", style="dim yellow")

    panel = Panel(
        summary_text,
        title="[bold white]📋 Your Configuration[/bold white]",
        border_style="blue",
        padding=(1, 2),
    )

    console.print(panel)
    console.print()

    logger.info(
        f"Configuration summary: agent={config.display_name}, "
        f"port={config.agent_port}, env={config.env}"
    )


class UserAbortError(typer.Abort):
    """Custom exception for user aborting the setup."""

    pass


def collect_configuration(default: bool, advanced: bool) -> AgentContext:
    """
    Interactive configuration wizard with delightful UX.
    """
    logger.info(
        f"Starting configuration wizard (default={default}, advanced={advanced})"
    )
    config = AgentContext()

    if default:
        logger.info("Using quick start mode with default configuration")
        console.clear()
        console.print()
        console.print("[bold green]   ⚡ Quick Start Mode[/bold green]")
        _success("Using default configuration for rapid setup")
        _display_summary(config)
        return config

    # Welcome screen
    console.clear()
    console.print()

    welcome_panel = Panel(
        "[bold white]🚀 AgentVerse Agent Setup[/bold white]\n\n"
        "[dim]Welcome! Let's create your agent together.\n"
        "Press Ctrl+C anytime to cancel.[/dim]",
        border_style="magenta",
        padding=(1, 2),
    )
    console.print(welcome_panel)
    logger.debug("Welcome screen displayed")

    # Collect configuration in sections
    _collect_agent_info(config, skip=default)

    if advanced:
        logger.debug("Advanced mode enabled")
        console.print()
        configure_hosting = Confirm.ask(
            "   [bold]🌐 Configure custom hosting settings?[/bold]",
            default=False,
            console=console,
        )
        logger.debug(f"Configure hosting: {configure_hosting}")
        _collect_hosting_info(config, skip=not configure_hosting)

        console.print()
        configure_env = Confirm.ask(
            "   [bold]⚙️  Configure environment & API keys?[/bold]",
            default=True,
            console=console,
        )
        logger.debug(f"Configure environment: {configure_env}")
        _collect_environment_and_keys(config, skip=not configure_env)
    else:
        logger.debug("Standard mode - skipping advanced options")
        _collect_hosting_info(config, skip=True)
        _collect_environment_and_keys(config, skip=True)

    # Display summary and confirm
    _display_summary(config)

    if not Confirm.ask(
        "   [bold green]✨ Ready to create your agent?[/bold green]",
        default=True,
        console=console,
    ):
        logger.warning("User cancelled setup at confirmation")
        console.print()
        console.print("[red]   ✖ Setup cancelled[/red]")
        raise UserAbortError()

    console.print()
    _success("Configuration complete! Creating your agent...")
    logger.info("Configuration wizard completed successfully")
    return config
