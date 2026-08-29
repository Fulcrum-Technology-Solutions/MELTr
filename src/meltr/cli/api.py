"""API server management CLI commands."""

import os
import sys
from typing import Optional

import click.exceptions
import typer
from rich.console import Console

from meltr.service import LogForgeService

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
        console.print(f"[dim]Logs: LOGFORGE_HOME/logs — stop: logforge stop | kill {pid}[/dim]")
        # Parent must not return through Typer/Click (Exit is caught as Exception in some versions).
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
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
    except (typer.Exit, click.exceptions.Exit):
        # Clean CLI exits must not hit the generic Exception handler (Typer vs Click class names differ by version).
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


@app.command("stop")
def api_stop(
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Seconds to wait after SIGTERM before SIGKILL",
    ),
) -> None:
    """Stop the LogForge daemon (PID from LOGFORGE_HOME/run/meltr.pid)."""
    import os
    import signal
    import time

    from meltr.core.paths import get_logforge_home
    from meltr.core.pidfile import (
        cmdline_suggests_logforge,
        read_service_pid,
        remove_service_pidfile,
    )

    if not hasattr(os, "kill"):
        console.print("[red]logforge stop requires a POSIX system with os.kill[/red]")
        raise typer.Exit(code=1)

    home = get_logforge_home()
    pid = read_service_pid(home)
    if pid is None:
        console.print(
            f"[yellow]No PID file at {home / 'run' / 'meltr.pid'} — nothing to stop.[/yellow]"
        )
        raise typer.Exit(code=0)

    if pid == os.getpid():
        console.print("[red]Refusing to stop: PID file points at this CLI process[/red]")
        raise typer.Exit(code=1)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        console.print(f"[yellow]Stale PID file (process {pid} gone); removing it.[/yellow]")
        remove_service_pidfile(home)
        raise typer.Exit(code=0) from None
    except PermissionError:
        console.print(
            f"[red]No permission to signal PID {pid}. "
            "Run as the same user as the service (or root).[/red]"
        )
        raise typer.Exit(code=1) from None

    if not cmdline_suggests_logforge(pid):
        console.print(
            f"[red]PID {pid} does not appear to be LogForge; refusing to kill.[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[green]Stopping LogForge (PID {pid})...[/green]")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        remove_service_pidfile(home)
        console.print("[green]LogForge already stopped.[/green]")
        raise typer.Exit(code=0) from None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            remove_service_pidfile(home)
            console.print("[green]LogForge stopped.[/green]")
            raise typer.Exit(code=0) from None
        time.sleep(0.2)

    console.print(f"[yellow]Still running after {timeout}s; sending SIGKILL[/yellow]")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    remove_service_pidfile(home)
    console.print("[green]LogForge stopped.[/green]")

