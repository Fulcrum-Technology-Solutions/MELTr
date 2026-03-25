"""Main CLI entry point."""

import sys
from typing import Optional

import typer
from rich.console import Console

from logforge import __version__
from logforge.cli import api, api_client, config, dashboard, entities, generators, service, templates
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
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Service user to create or use (default: logmgr)"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Service group (default: same as user)"),
    create_user: Optional[bool] = typer.Option(
        None,
        "--create-user/--no-create-user",
        help="Create service user/group if missing (default: yes when root, no when non-root)",
    ),
) -> None:
    """Initialize LogForge configuration and directory structure."""
    init(directory=directory, interactive=interactive, force=force, user=user, group=group, create_user=create_user)

app.add_typer(config.app, name="config")
app.add_typer(entities.app, name="entities")
app.add_typer(templates.app, name="templates")
app.add_typer(generators.app, name="generators")
app.add_typer(api.app, name="api")
app.add_typer(service.app, name="service")
app.add_typer(dashboard.app, name="dashboard")

# Add start command (shortcut for api start)
@app.command("start")
def start(
    host: Optional[str] = typer.Option(None, "--host", help="API server host"),
    port: Optional[int] = typer.Option(None, "--port", help="API server port"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file path"),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Stay attached to the terminal (default is to background on POSIX, like Splunk/Cribl CLI start)",
    ),
) -> None:
    """Start the LogForge service and API server."""
    from logforge.cli.api import api_start
    api_start(host=host, port=port, config=config, foreground=foreground)


@app.command("stop")
def stop_command(
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Seconds to wait after SIGTERM before SIGKILL",
    ),
) -> None:
    """Stop the LogForge service (PID file under LOGFORGE_HOME/run/)."""
    from logforge.cli.api import api_stop

    api_stop(timeout=timeout)


# Add status command (shortcut for generators status)
@app.command("status")
def status(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
) -> None:
    """Show status of all generators."""
    from logforge.cli.generators import generators_status
    generators_status(None, api_url, api_key, timeout)



@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL", help="API server URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY", help="API key for authentication"),
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
) -> None:
    """LogForge CLI - Manage synthetic event log generation."""
    # Handle --version flag
    if version:
        console.print(f"LogForge {__version__}")
        raise typer.Exit()
    
    # If no command provided, let Typer show help (no_args_is_help=True)
    if ctx.invoked_subcommand is None:
        return
    
    # Store API settings in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['api_url'] = api_url
    ctx.obj['api_key'] = api_key


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

