import logging
from importlib.metadata import version
from typing import Annotated
from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from .prompts import UserAbortError

logger = logging.getLogger("create-agentverse-agent")

app = typer.Typer(
    help="✨ Create an AgentVerse agent with style.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


class CLIStopExecution(typer.Exit):
    """Custom exception to stop CLI execution."""

    pass


def version_callback(show_version: bool) -> None:
    """Show version and exit."""
    if show_version:
        app_version = version("create-agentverse-agent")
        console.print(
            f"[bold cyan]create-agentverse-agent[/bold cyan] version [green]{app_version}[/green]"
        )
        raise CLIStopExecution()


@app.command()
def main(
    default: Annotated[
        bool,
        typer.Option(
            "--default",
            "-d",
            help="Quick start with default values",
        ),
    ] = False,
    advanced: Annotated[
        bool,
        typer.Option(
            "--advanced",
            "-a",
            help="Advanced mode with all configuration options",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help="Overwrite existing project if it exists",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Show debug logs in 'create-agentverse-agent-<version>-cli-execution-<uuid>.log'",
        ),
    ] = False,
    _: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """
    Create an AgentVerse agent with an interactive wizard.

    [bold cyan]Examples:[/bold cyan]

      [dim]# Interactive setup[/dim]
      create-agentverse-agent

      [dim]# Quick start with defaults[/dim]
      create-agentverse-agent -d

      [dim]# Advanced configuration[/dim]
      create-agentverse-agent -a
    """
    # Set logging level based on verbose flag

    execution_id = f"create-agentverse-agent-{version('create-agentverse-agent')}-cli-execution-{uuid4()}"

    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            filename=f"{execution_id}.log",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger.debug("Verbose logging enabled")
    else:
        logging.basicConfig(
            level=logging.CRITICAL,
        )

    logger.debug(
        f"CLI options: default={default}, advanced={advanced}, overwrite={overwrite}"
    )

    try:
        from .prompts import collect_configuration

        logger.info("Starting configuration collection")
        config = collect_configuration(default=default, advanced=advanced)
        logger.debug(f"Configuration collected: display_name={config.display_name}")

        from .scaffold import Scaffolder
        from .templates import TemplateRenderer

        # Show progress with spinner
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Creating agent '{config.display_name}'...", total=None)

            logger.debug("Initializing template renderer")
            renderer = TemplateRenderer()

            logger.debug("Initializing scaffolder")
            scaffolder = Scaffolder(renderer)

            logger.info(f"Creating project with overwrite={overwrite}")
            project_path = scaffolder.create_project(config, overwrite=overwrite)
            logger.debug(f"Project created at: {project_path.absolute()}")

        # Success message with clear next steps
        if not default:
            console.clear()

        success_text = Text()
        success_text.append("🎉 Agent Created Successfully!", style="bold white")

        success_panel = Panel(
            success_text,
            border_style="green",
            padding=(1, 2),
        )
        console.print(success_panel)

        console.print()
        console.print("[bold cyan]   📍 Project Location[/bold cyan]")
        console.print(f"      [bold white]{project_path.absolute()}[/bold white]")

        console.print()
        console.print("[bold cyan]   🚀 Next Steps[/bold cyan]")

        step = 1

        if not config.is_api_keys_provided():
            console.print()
            console.print(f"   [bold yellow]{step}. Add your API keys[/bold yellow]")
            console.print("      Edit [white].env[/white] in your project directory:")
            console.print()
            if not config.agentverse_api_key:
                console.print("      [dim white]• AGENTVERSE_API_KEY[/dim white]")
            step += 1

        console.print()
        console.print(f"   [bold yellow]{step}. Start your agent[/bold yellow]")
        console.print()
        console.print("      [bold white]docker-compose up[/bold white]")

        console.print()
        console.print(
            "[dim blue]   ─────────────────────────────────────────────────────────[/dim blue]"
        )
        console.print(
            "[dim blue]   💡 Tip: Use 'docker-compose up -d' to run in background[/dim blue]"
        )
        console.print()

        logger.info("Agent created successfully")

    except UserAbortError:
        logger.warning("Setup cancelled by user")
        console.print()
        console.print()
        console.print("[yellow]   ✖  Setup cancelled by user[/yellow]")
        console.print()
        UserAbortError()

    except FileExistsError as e:
        logger.error(f"Project already exists: {e}")
        console.print()
        console.print("[bold red]   ✖  Error: Project already exists[/bold red]")
        console.print(f"[dim red]   {e}[/dim red]")
        console.print()
        console.print(
            "[dim yellow]   💡 Use --overwrite flag to replace the existing project[/dim yellow]"
        )
        console.print()
        typer.Abort()

    except KeyboardInterrupt:
        logger.warning("Setup interrupted by keyboard")
        console.print()
        console.print()
        console.print("[yellow]   ✖  Setup cancelled by user[/yellow]")
        console.print()
        UserAbortError()

    except Exception as e:
        logger.exception(f"Failed to create agent: {e}")
        console.print()
        console.print("[bold red]   ✖  Failed to create agent[/bold red]")
        console.print(f"[dim red]   {e}[/dim red]")
        console.print()
        typer.Abort()

    finally:
        logger.debug("CLI execution completed")
        if debug:
            console.print(
                f"[dim yellow]   💡 Debug log saved to '{execution_id}.log'[/dim yellow]"
            )
