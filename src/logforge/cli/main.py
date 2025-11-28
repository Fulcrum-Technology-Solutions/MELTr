"""Main CLI entry point."""

import sys
from typing import Optional

import typer
from rich.console import Console

from logforge.cli import api, api_client, config, entities, generators, templates
from logforge.cli.init import init

console = Console()

app = typer.Typer(
    name="logforge",
    help="LogForge - Synthetic event log generator",
    add_completion=False,
    no_args_is_help=True,
)

# Register subcommands
@app.command("init")
def init_command(
    directory: Optional[str] = typer.Option(None, "--directory", "-d", help="Installation directory (default: ./logforge)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run interactive wizard"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration"),
) -> None:
    """Initialize LogForge configuration and directory structure."""
    init(directory=directory, interactive=interactive, force=force)

app.add_typer(config.app, name="config")
app.add_typer(entities.app, name="entities")
app.add_typer(templates.app, name="templates")
app.add_typer(generators.app, name="generators")
app.add_typer(api.app, name="api")

# Add start command (shortcut for api start)
@app.command("start")
def start(
    host: Optional[str] = typer.Option(None, "--host", help="API server host"),
    port: Optional[int] = typer.Option(None, "--port", help="API server port"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Start the LogForge service and API server."""
    from logforge.cli.api import api_start
    api_start(host=host, port=port, config=config)

# Add status command (shortcut for generators status)
@app.command("status")
def status(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
) -> None:
    """Show status of all generators."""
    from logforge.cli.generators import generators_status
    generators_status(None, api_url, api_key)


@app.callback()
def main_callback(
    ctx: typer.Context,
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL", help="API server URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY", help="API key for authentication"),
) -> None:
    """LogForge CLI - Manage synthetic event log generation."""
    # Store API settings in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['api_url'] = api_url
    ctx.obj['api_key'] = api_key


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

