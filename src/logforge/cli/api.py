"""API server management CLI commands."""

import os
import sys
from typing import Optional

import typer
from rich.console import Console

from logforge.service import LogForgeService

app = typer.Typer(name="api", help="API server management")
console = Console()


def _must_stay_foreground() -> bool:
    """True when a supervisor (systemd, notify) expects the main process to stay attached."""
    env = os.environ.get
    if env("LOGFORGE_FOREGROUND", "").lower() in ("1", "true", "yes"):
        return True
    # systemd service manager sets INVOCATION_ID on units
    if env("INVOCATION_ID"):
        return True
    if env("NOTIFY_SOCKET"):
        return True
    return False


def _detach_from_terminal() -> None:
    """Background this process: new session, no controlling tty (POSIX).

    Must be called before LogForgeService is constructed so we never fork after threads start.
    """
    pid = os.fork()
    if pid > 0:
        console.print(f"[green]LogForge started in background (PID {pid}).[/green]")
        console.print(f"[dim]Logs: LOGFORGE_HOME/logs — stop: kill {pid}[/dim]")
        raise typer.Exit(0)
    os.setsid()
    devnull_in = open(os.devnull, "rb")
    devnull_out = open(os.devnull, "wb")
    os.dup2(devnull_in.fileno(), sys.stdin.fileno())
    os.dup2(devnull_out.fileno(), sys.stdout.fileno())
    os.dup2(devnull_out.fileno(), sys.stderr.fileno())
    devnull_in.close()
    devnull_out.close()


@app.command("start")
def api_start(
    host: Optional[str] = typer.Option(None, "--host", help="API server host"),
    port: Optional[int] = typer.Option(None, "--port", help="API server port"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file path"),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Stay in the foreground (logs to terminal). systemd uses this automatically via unit file.",
    ),
) -> None:
    """Start the LogForge API server and service."""
    from pathlib import Path

    config_path = Path(config) if config else None

    try:
        if not foreground and not _must_stay_foreground():
            if hasattr(os, "fork"):
                _detach_from_terminal()
            else:
                console.print(
                    "[yellow]Fork not available; running in foreground "
                    "(use your service manager to run LogForge in the background).[/yellow]"
                )
        service = LogForgeService(config_path=config_path)

        if host:
            service.config.api.host = host
        if port:
            service.config.api.port = port

        service.run()
    except typer.Exit:
        # Parent return from daemonize uses typer.Exit(0); must not be treated as failure.
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        import traceback
        console.print(f"[red]Error: {e}[/red]")
        # Print full traceback for debugging
        console.print("[red]Traceback:[/red]")
        console.print(traceback.format_exc())
        raise typer.Exit(code=1) from None

