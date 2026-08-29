"""Main CLI entry point."""

import typer
from rich.console import Console

from meltr import __version__
from meltr.cli import api, config, dashboard, entities, generators, service, templates
from meltr.cli.init import init

console = Console()

app = typer.Typer(
    name="meltr",
    help="MELTr - Synthetic event log generator",
    add_completion=False,
    no_args_is_help=True,
)


# Register subcommands
@app.command("init")
def init_command(
    directory: str | None = typer.Option(
        None, "--directory", "-d", help="Installation directory (default: ./meltr)"
    ),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run interactive wizard"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration"),
    user: str | None = typer.Option(
        None, "--user", "-u", help="Service user to create or use (default: meltr)"
    ),
    group: str | None = typer.Option(
        None, "--group", "-g", help="Service group (default: same as user)"
    ),
    create_user: bool | None = typer.Option(
        None,
        "--create-user/--no-create-user",
        help="Create service user/group if missing (default: yes when root, no when non-root)",
    ),
) -> None:
    """Initialize MELTr configuration and directory structure."""
    init(
        directory=directory,
        interactive=interactive,
        force=force,
        user=user,
        group=group,
        create_user=create_user,
    )


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
    host: str | None = typer.Option(None, "--host", help="API server host"),
    port: int | None = typer.Option(None, "--port", help="API server port"),
    config: str | None = typer.Option(None, "--config", help="Config file path"),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Stay attached to the terminal (default is to background on POSIX, like Splunk/Cribl CLI start)",
    ),
) -> None:
    """Start the MELTr service and API server."""
    from meltr.cli.api import api_start

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
    """Stop the MELTr service (PID file under MELTR_HOME/run/)."""
    from meltr.cli.api import api_stop

    api_stop(timeout=timeout)


@app.command("restart")
def restart_command(
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Seconds to wait after SIGTERM before SIGKILL (local stop fallback)",
    ),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Stay attached to the terminal for local restart fallback",
    ),
) -> None:
    """Restart MELTr (prefer systemd if integrated, otherwise local PID-file stop/start)."""
    from meltr.cli.api import api_start, api_stop
    from meltr.cli.restart import restart

    restart(
        timeout=timeout,
        foreground=foreground,
        console=console,
        api_stop=api_stop,
        api_start=api_start,
    )


# Add status command (shortcut for generators status)
@app.command("status")
def status(
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
) -> None:
    """Show status of all generators."""
    from meltr.cli.generators import generators_status

    generators_status(None, api_url, api_key, timeout)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_API_URL", help="API server URL"
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", envvar="MELTR_API_KEY", help="API key for authentication"
    ),
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
) -> None:
    """MELTr CLI - Manage synthetic event log generation."""
    # Handle --version flag
    if version:
        console.print(f"MELTr {__version__}")
        raise typer.Exit()

    # If no command provided, let Typer show help (no_args_is_help=True)
    if ctx.invoked_subcommand is None:
        return

    # Store API settings in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["api_key"] = api_key


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
