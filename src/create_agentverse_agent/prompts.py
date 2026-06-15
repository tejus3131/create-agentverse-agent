import logging
import re
from typing import Literal, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from .context import (
    ContextError,
    PaymentMethodState,
    ProjectContext,
)

logger = logging.getLogger(__name__)

console = Console()

_HANDLE_PATTERN = re.compile(r"^[a-z0-9-]+$")


def header(text: str, emoji: str = "✨") -> None:
    """Display a stylish section header."""
    console.print()
    console.print(f"[bold cyan]{emoji}  {text}[/bold cyan]")
    console.print(f"[dim blue]   {'─' * (len(text) + 2)}[/dim blue]")


def success(text: str) -> None:
    """Display a success message."""
    logger.info(text)
    console.print(f"[dim green]   ✓ {text}[/dim green]")


def hint(text: str) -> None:
    """Display a helpful hint."""
    console.print(f"[dim yellow]   💡 {text}[/dim yellow]")


def prompt_with_style(
    prompt_text: str,
    default: str | None = None,
    password: bool = False,
) -> str:
    """Styled prompt wrapper."""
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
    return result


def prompt_int(prompt_text: str, default: int, *, minimum: int | None = None) -> int:
    """Prompt for integer input with optional minimum."""
    while True:
        response = prompt_with_style(prompt_text, default=str(default))
        try:
            value = int(response)
            if minimum is not None and value < minimum:
                console.print(f"[red]   Value must be >= {minimum}[/red]")
                continue
            return value
        except ValueError:
            console.print("[red]   Please enter a valid number[/red]")


def prompt_choice(prompt_text: str, choices: list[str], default: str) -> str:
    """Prompt for choice input."""
    formatted_choices = " / ".join(f"[cyan]{c}[/cyan]" for c in choices)
    full_prompt = f"   [bold white]{prompt_text}[/bold white] ({formatted_choices})"
    while True:
        response = Prompt.ask(
            full_prompt,
            default=default,
            console=console,
        ).lower()
        if response in [c.lower() for c in choices]:
            return response
        console.print(f"[red]   Please choose one of: {', '.join(choices)}[/red]")


def prompt_handle(prompt_text: str, default: str) -> str:
    """Prompt for agent handle slug."""
    while True:
        value = prompt_with_style(prompt_text, default=default).lower().strip()
        if _HANDLE_PATTERN.match(value):
            return value
        console.print(
            "[red]   Handle must be lowercase letters, numbers, and dashes[/red]"
        )


def collect_identity(config: ProjectContext, skip: bool = False) -> None:
    """Collect agent identity."""
    if skip:
        success("Using default agent identity")
        return

    header("Agent Identity", "🤖")
    agent = config.yml.agent
    agent.name = prompt_with_style("Agent name", default=agent.name)
    agent.handle = prompt_handle("Agent handle (URL slug)", default=agent.handle)
    config.project_name = agent.handle
    agent.description = prompt_with_style("Description", default=agent.description)
    agent.port = prompt_int("Agent port", default=agent.port, minimum=1024)
    console.print()


def collect_network(config: ProjectContext, skip: bool = False) -> None:
    """Collect network selection."""
    if skip:
        success("Using default network (testnet)")
        return

    header("Network", "🌐")
    config.yml.runtime.network = cast(
        Literal["testnet", "mainnet"],
        prompt_choice(
            "Which Fetch network?",
            choices=["testnet", "mainnet"],
            default=config.yml.runtime.network,
        ),
    )
    console.print()


def collect_postgres(config: ProjectContext, skip: bool = False) -> None:
    """Collect Postgres connection settings."""
    if skip:
        success("Using default Postgres settings")
        return

    header("Postgres", "🗄️")
    secrets = config.secrets
    secrets.postgres_host = prompt_with_style("Host", default=secrets.postgres_host)
    secrets.postgres_port = prompt_int("Port", default=secrets.postgres_port, minimum=1)
    secrets.postgres_database = prompt_with_style(
        "Database", default=secrets.postgres_database
    )
    secrets.postgres_user = prompt_with_style("User", default=secrets.postgres_user)
    secrets.postgres_password = prompt_with_style(
        "Password",
        default=secrets.postgres_password,
        password=True,
    )
    console.print()


def collect_agentverse(config: ProjectContext, skip: bool = False) -> None:
    """Collect optional Agentverse credentials."""
    if skip:
        success("Skipping Agentverse credentials")
        return

    header("Agentverse", "🔑")
    hint("Optional — set AGENTVERSE_API_KEY in .env later to enable registration")

    if Confirm.ask(
        "   [bold]Add Agentverse API key now?[/bold]", default=False, console=console
    ):
        config.secrets.agentverse_api_key = prompt_with_style(
            "Agentverse API key",
            password=True,
        )

    if Confirm.ask(
        "   [bold]Set agent seed now?[/bold]", default=False, console=console
    ):
        config.secrets.agent_seed = prompt_with_style(
            "Agent seed",
            default=config.secrets.agent_seed,
            password=True,
        )
    console.print()


def collect_payment_methods(config: ProjectContext, skip: bool = False) -> None:
    """Collect payment method toggles and provider secrets."""
    if skip:
        success("Using default payment methods (FET only)")
        return

    header("Payments", "💳")
    methods = config.yml.protocols.payment.methods

    methods.fet = PaymentMethodState(
        prompt_choice(
            "FET payments", ["enabled", "disabled"], default=methods.fet.value
        )
    )
    methods.stripe = PaymentMethodState(
        prompt_choice(
            "Stripe payments", ["enabled", "disabled"], default=methods.stripe.value
        )
    )
    methods.skyfire = PaymentMethodState(
        prompt_choice(
            "Skyfire payments", ["enabled", "disabled"], default=methods.skyfire.value
        )
    )

    secrets = config.secrets
    if methods.stripe is PaymentMethodState.ENABLED:
        secrets.stripe_secret_key = prompt_with_style(
            "Stripe secret key", password=True
        )
        secrets.stripe_publishable_key = prompt_with_style(
            "Stripe publishable key", password=True
        )
    if methods.skyfire is PaymentMethodState.ENABLED:
        secrets.skyfire_api_key = prompt_with_style("Skyfire API key", password=True)
        secrets.skyfire_seller_account_id = prompt_with_style(
            "Skyfire seller account ID", password=True
        )
        secrets.skyfire_service_id = prompt_with_style(
            "Skyfire service ID", password=True
        )
    console.print()


def collect_advanced_runtime(config: ProjectContext, skip: bool = False) -> None:
    """Collect advanced runtime and protocol settings."""
    if skip:
        success("Using default advanced settings")
        return

    header("Advanced Settings", "🔧")
    runtime = config.yml.runtime
    runtime.log_level = cast(
        Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        prompt_choice(
            "Log level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=runtime.log_level,
        ),
    )
    runtime.max_concurrent_sessions = prompt_int(
        "Max concurrent sessions",
        default=runtime.max_concurrent_sessions,
        minimum=1,
    )

    for protocol_name in ("chat", "payment"):
        protocol = getattr(config.yml.protocols, protocol_name)
        protocol.maximum_processing_time_seconds = prompt_int(
            f"{protocol_name} max processing time (seconds)",
            default=protocol.maximum_processing_time_seconds,
            minimum=1,
        )
        protocol.rate_limits.session.max_requests = prompt_int(
            f"{protocol_name} session max requests",
            default=protocol.rate_limits.session.max_requests,
            minimum=1,
        )
        protocol.rate_limits.user.max_requests = prompt_int(
            f"{protocol_name} user max requests",
            default=protocol.rate_limits.user.max_requests,
            minimum=1,
        )
    console.print()


def display_summary(config: ProjectContext) -> None:
    """Display configuration summary."""
    console.print()
    summary = Text()
    agent = config.yml.agent
    runtime = config.yml.runtime
    methods = config.yml.protocols.payment.methods

    summary.append("🤖 Agent\n", style="bold cyan")
    summary.append(f"   Name  : {agent.name}\n", style="white")
    summary.append(f"   Handle: {agent.handle}\n", style="white")
    summary.append(f"   Port  : {agent.port}\n\n", style="white")

    summary.append("🌐 Runtime\n", style="bold cyan")
    summary.append(f"   Network : {runtime.network}\n", style="white")
    summary.append(f"   Log     : {runtime.log_level}\n\n", style="white")

    summary.append("🗄️  Postgres\n", style="bold cyan")
    summary.append(f"   Host : {config.secrets.postgres_host}\n", style="white")
    summary.append(f"   Port : {config.secrets.postgres_port}\n", style="white")
    summary.append(f"   DB   : {config.secrets.postgres_database}\n\n", style="white")

    summary.append("💳 Payments\n", style="bold cyan")
    summary.append(
        f"   FET={methods.fet.value}  Stripe={methods.stripe.value}  "
        f"Skyfire={methods.skyfire.value}\n\n",
        style="white",
    )

    summary.append("🔑 Agentverse\n", style="bold cyan")
    if config.secrets.agentverse_api_key:
        summary.append("   API key: set\n", style="green")
    else:
        summary.append("   API key: not set\n", style="yellow")

    panel = Panel(
        summary,
        title="[bold white]📋 Your Configuration[/bold white]",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def divider() -> None:
    """Print a divider line."""
    console.print()
    console.print("[dim blue]" + "─" * console.width + "[/dim blue]")
    console.print()


class UserAbortError(typer.Abort):
    """Custom exception for user aborting the setup."""


def collect_configuration(default: bool, advanced: bool) -> ProjectContext:
    """Interactive configuration wizard."""
    if default:
        console.clear()
        console.print()
        console.print("[bold green]   ⚡ Quick Start Mode[/bold green]")
        config = ProjectContext.create_default()
        success("Using default configuration for rapid setup")
        display_summary(config)
        return config

    console.clear()
    console.print()
    welcome = Panel(
        "[bold white]🚀 uAgents Project Setup[/bold white]\n\n"
        "[dim]Scaffold a production-ready multipod uAgents project.\n"
        "Press Ctrl+C anytime to cancel.[/dim]",
        border_style="magenta",
        padding=(1, 2),
    )
    console.print(welcome)

    config = ProjectContext.create_default()
    collect_identity(config, skip=False)
    collect_network(config, skip=False)
    collect_postgres(config, skip=False)
    collect_agentverse(config, skip=False)

    if advanced:
        divider()
        if Confirm.ask(
            "[bold]💳 Configure payment methods?[/bold]", default=False, console=console
        ):
            collect_payment_methods(config, skip=False)
        else:
            collect_payment_methods(config, skip=True)

        divider()
        if Confirm.ask(
            "[bold]🔧 Configure advanced runtime settings?[/bold]",
            default=False,
            console=console,
        ):
            collect_advanced_runtime(config, skip=False)
        else:
            collect_advanced_runtime(config, skip=True)
    else:
        collect_payment_methods(config, skip=True)
        collect_advanced_runtime(config, skip=True)

    display_summary(config)

    if not Confirm.ask(
        "   [bold green]✨ Ready to create your project?[/bold green]",
        default=True,
        console=console,
    ):
        console.print()
        console.print("[red]   ✖ Setup cancelled[/red]")
        raise UserAbortError()

    console.print()
    success("Configuration complete! Creating your project...")
    try:
        return config.revalidated()
    except ContextError as exc:
        console.print(f"[red]   ✖ Invalid configuration: {exc}[/red]")
        raise UserAbortError() from exc
