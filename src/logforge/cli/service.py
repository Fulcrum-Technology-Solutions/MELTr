"""Systemd service management CLI commands."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

try:
    import grp
    import pwd
except ImportError:
    grp = None
    pwd = None

import typer
from rich.console import Console

from logforge.cli.user_utils import ensure_service_user_and_group
from logforge.core.paths import get_install_root_from_binary, get_logforge_home

app = typer.Typer(name="service", help="Systemd service management")
console = Console()

SERVICE_FILE = """[Unit]
Description=LogForge Synthetic Event Generator
After=network.target

[Service]
Type=simple
User={service_user}
Group={service_group}
WorkingDirectory={logforge_home}
ExecStart={logforge_bin} api start --foreground
Restart=on-failure
RestartSec=10s
TimeoutStartSec=90
LimitNOFILE=65536

# Environment
Environment="LOGFORGE_HOME={logforge_home}"

# Optional: override application log path (default: <install_root>/logs/logforge.log)
# Environment="LOGFORGE_LOG_FILE=/path/to/logforge.log"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=logforge

[Install]
WantedBy=multi-user.target
"""


def _get_logforge_binary_path() -> Path:
    """Get path to logforge binary.

    Returns:
        Path to logforge executable
    """
    logforge_path = shutil.which('logforge')
    if logforge_path:
        return Path(logforge_path).resolve()

    # /opt: official tarball layout app/bin/logforge, or dev .venv (casing: LogForge)
    opt = Path('/opt')
    if opt.exists():
        for p in opt.iterdir():
            if p.is_dir() and p.name.lower() == 'logforge':
                bundle_bin = p / 'app' / 'bin' / 'logforge'
                if bundle_bin.is_file():
                    return bundle_bin.resolve()
                venv_bin = p / '.venv' / 'bin' / 'logforge'
                if venv_bin.exists():
                    return venv_bin.resolve()
                break

    for path in ['/usr/local/bin/logforge', '/usr/bin/logforge']:
        if Path(path).exists():
            return Path(path).resolve()

    venv_bin = Path(os.environ.get('VIRTUAL_ENV', '')) / 'bin' / 'logforge'
    if venv_bin.exists():
        return venv_bin.resolve()

    raise RuntimeError("Could not find logforge binary. Install it system-wide or activate virtual environment.")


def _check_root() -> None:
    """Check if running as root.
    
    Raises:
        typer.Exit: If not running as root
    """
    if os.geteuid() != 0:
        console.print("[red]Error: This command requires root privileges[/red]")
        console.print("[yellow]Hint: Use 'sudo logforge service <command>'[/yellow]")
        raise typer.Exit(code=1)


@app.command("install")
def service_install(
    logforge_home: Optional[str] = typer.Option(None, "--home", help="LOGFORGE_HOME directory"),
    logforge_bin: Optional[str] = typer.Option(None, "--binary", help="Path to logforge binary"),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User to run service as (default: logmgr)"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Group to run service as (default: same as user)"),
    create_user: bool = typer.Option(True, "--create-user/--no-create-user", help="Create service user if it doesn't exist"),
) -> None:
    """Install LogForge as a systemd service.

    Use --home /var/lib/logforge for the service data directory (default when run as root).
    Use --user logmgr --no-create-user when the user already exists.
    Example:
        sudo logforge service install --user logmgr --group logmgr --home /var/lib/logforge
    """
    _check_root()

    try:
        service_user = user or 'logmgr'
        service_group = group or service_user

        if logforge_home:
            home_path = Path(logforge_home).expanduser().resolve()
        else:
            home_path = get_logforge_home()

        if logforge_bin:
            bin_path = Path(logforge_bin).expanduser().resolve()
        else:
            bin_path = _get_logforge_binary_path()

        if not bin_path.exists():
            console.print(f"[red]Error: LogForge binary not found at {bin_path}[/red]")
            raise typer.Exit(code=1)

        console.print("[green]Installing LogForge systemd service...[/green]")
        console.print(f"  Service user: {service_user}")
        console.print(f"  Service group: {service_group}")
        console.print(f"  LOGFORGE_HOME: {home_path}")

        home_path.mkdir(parents=True, exist_ok=True)

        service_uid, service_gid = ensure_service_user_and_group(
            service_user,
            service_group,
            home_path,
            create_user,
            on_user_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_group_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_user_exists=lambda msg: console.print(f"[yellow]⚠ {msg}[/yellow]"),
            on_no_pwd_grp=lambda: console.print("[yellow]⚠ pwd/grp modules not available, skipping user/group creation[/yellow]"),
            on_useradd_missing=lambda: console.print("[yellow]⚠ useradd/groupadd not found, skipping user/group creation[/yellow]"),
        )

        if service_uid == 0 and service_gid == 0 and (pwd is None or grp is None):
            console.print("[yellow]⚠ pwd/grp modules not available, using root ownership[/yellow]")
            console.print("[yellow]⚠ Service may not start correctly[/yellow]")
        elif service_uid == 0 and service_gid == 0:
            console.print(f"[yellow]⚠ Could not get {service_user} user info - using root ownership[/yellow]")
            console.print("[yellow]⚠ Service may not start correctly[/yellow]")

        # Set ownership to service user so service can write
        if service_uid is not None and (service_uid, service_gid) != (0, 0):
            os.chown(home_path, service_uid, service_gid)
            parent = home_path.parent
            if parent.exists():
                if parent.name.lower() == 'logforge':
                    os.chown(parent, service_uid, service_gid)
                elif parent.name == 'data' and parent.parent.name.lower() == 'logforge' and parent.parent.exists():
                    os.chown(parent.parent, service_uid, service_gid)

        install_root = get_install_root_from_binary(bin_path)
        if install_root is not None:
            app_log_dir = install_root / 'logs'
            app_log_dir.mkdir(parents=True, exist_ok=True)
            if service_uid is not None and (service_uid, service_gid) != (0, 0):
                os.chown(app_log_dir, service_uid, service_gid)
        else:
            log_dir = Path('/var/log/logforge')
            log_dir.mkdir(parents=True, exist_ok=True)
            if service_uid is not None and (service_uid, service_gid) != (0, 0):
                os.chown(log_dir, service_uid, service_gid)

        # Create service file
        service_content = SERVICE_FILE.format(
            logforge_home=str(home_path),
            logforge_bin=str(bin_path),
            service_user=service_user,
            service_group=service_group,
        )

        service_file_path = Path('/etc/systemd/system/logforge.service')
        service_file_path.write_text(service_content)
        console.print(f"[green]✓ Created service file: {service_file_path}[/green]")

        # Reload systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        console.print("[green]✓ Reloaded systemd daemon[/green]")

        console.print("\n[green]Service installed successfully![/green]")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("  sudo systemctl start logforge")
        console.print("  sudo systemctl enable logforge  # Start on boot")
        console.print("  sudo systemctl status logforge")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("uninstall")
def service_uninstall() -> None:
    """Uninstall LogForge systemd service.

    Removes only the systemd unit and reloads systemd. Data under LOGFORGE_HOME,
    install-tree logs under ``<install_root>/logs``, and ``/var/log/logforge`` (if used)
    are left intentionally.
    """
    _check_root()

    try:
        # Stop and disable service
        subprocess.run(['systemctl', 'stop', 'logforge'], check=False)
        subprocess.run(['systemctl', 'disable', 'logforge'], check=False)

        # Remove service file
        service_file = Path('/etc/systemd/system/logforge.service')
        if service_file.exists():
            service_file.unlink()
            console.print("[green]✓ Removed service file[/green]")

        # Reload systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        console.print("[green]✓ Service uninstalled[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("start")
def service_start() -> None:
    """Start the systemd service."""
    _check_root()

    try:
        subprocess.run(['systemctl', 'start', 'logforge'], check=True)
        console.print("[green]✓ Service started[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("stop")
def service_stop() -> None:
    """Stop the systemd service."""
    _check_root()

    try:
        subprocess.run(['systemctl', 'stop', 'logforge'], check=True)
        console.print("[green]✓ Service stopped[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("restart")
def service_restart() -> None:
    """Restart the systemd service."""
    _check_root()

    try:
        subprocess.run(['systemctl', 'restart', 'logforge'], check=True)
        console.print("[green]✓ Service restarted[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("status")
def service_status() -> None:
    """Show systemd service status (no root required)."""
    try:
        # Run systemctl status and capture output
        result = subprocess.run(
            ['systemctl', 'status', 'logforge', '--no-pager'],
            capture_output=True,
            text=True,
        )
        console.print(result.stdout)
        if result.stderr:
            console.print(result.stderr)

        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

