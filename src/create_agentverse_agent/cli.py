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
from .scaffold import ScaffoldError

logger = logging.getLogger("create-agentverse-agent")

app = typer.Typer(
    help="✨ Scaffold a production-ready uAgents project.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


class CLIStopExecution(typer.Exit):
    """Custom exception to stop CLI execution."""


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
            help="Write debug log to create-agentverse-agent-<version>-cli-execution-<uuid>.log",
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
    Scaffold a production-ready uAgents project with an interactive wizard.

    [bold cyan]Examples:[/bold cyan]

      [dim]# Interactive setup[/dim]
      create-agentverse-agent

      [dim]# Quick start with defaults[/dim]
      create-agentverse-agent -d

      [dim]# Advanced configuration[/dim]
      create-agentverse-agent -a
    """
    execution_id = (
        f"create-agentverse-agent-{version('create-agentverse-agent')}"
        f"-cli-execution-{uuid4()}"
    )

    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            filename=f"{execution_id}.log",
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        logging.basicConfig(level=logging.CRITICAL)

    try:
        from .prompts import collect_configuration
        from .scaffold import Scaffolder
        from .templates import TemplateRenderer

        config = collect_configuration(default=default, advanced=advanced)

        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(
                f"Creating project '{config.display_name}'...", total=None
            )
            renderer = TemplateRenderer()
            scaffolder = Scaffolder(renderer)
            project_path = scaffolder.create_project(config, overwrite=overwrite)

        success_text = Text()
        success_text.append("📍 Project Location\n", style="bold cyan")
        success_text.append(f"   {project_path.absolute()}\n", style="bold white")
        success_text.append("\n")
        success_text.append("🚀 Next Steps\n", style="bold cyan")
        success_text.append("\n")
        success_text.append("1. Navigate to your project\n", style="bold yellow")
        success_text.append(f"   cd {project_path}\n", style="bold white")
        success_text.append("\n")
        success_text.append("2. Install dependencies\n", style="bold yellow")
        success_text.append("   uv sync\n", style="bold white")
        success_text.append("\n")
        success_text.append("3. Run locally\n", style="bold yellow")
        success_text.append("   make test\n", style="bold white")
        success_text.append("\n")
        success_text.append("─" * 57 + "\n", style="dim blue")
        success_text.append(
            "💡 make help — db, test, run, down | edit src/agent/handler.py",
            style="dim blue",
        )

        if not config.is_agentverse_configured():
            success_text.append("\n\n")
            success_text.append(
                "⚠️  Add AGENTVERSE_API_KEY to .env for Agentverse registration",
                style="yellow",
            )

        console.print(
            Panel(
                success_text,
                title="Project Created Successfully!",
                border_style="green",
                padding=(1, 2),
            )
        )
        console.print()

    except UserAbortError:
        console.print()
        console.print("[yellow]   ✖  Setup cancelled by user[/yellow]")
        console.print()
        raise typer.Abort() from None

    except ScaffoldError as exc:
        console.print()
        console.print("[bold red]   ✖  Error: Project already exists[/bold red]")
        console.print(f"[dim red]   {exc}[/dim red]")
        console.print()
        console.print(
            "[dim yellow]   💡 Use --overwrite flag to replace the existing project[/dim yellow]"
        )
        console.print()
        raise typer.Abort() from exc

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]   ✖  Setup cancelled by user[/yellow]")
        console.print()
        raise typer.Abort() from None

    except Exception as exc:
        logger.exception("Failed to create project: %s", exc)
        console.print()
        console.print("[bold red]   ✖  Failed to create project[/bold red]")
        console.print(f"[dim red]   {exc}[/dim red]")
        console.print()
        raise typer.Abort() from exc

    finally:
        if debug:
            console.print(
                f"[dim yellow]   💡 Debug log saved to '{execution_id}.log'[/dim yellow]"
            )
