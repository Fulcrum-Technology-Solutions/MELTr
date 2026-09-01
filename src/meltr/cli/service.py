"""Systemd service management CLI commands."""

import os
import shutil
import subprocess
from pathlib import Path

try:
    import grp
    import pwd
except ImportError:
    grp = None
    pwd = None

import typer
from rich.console import Console

from meltr.cli.path_helpers import write_operator_path_helpers
from meltr.cli.user_utils import ensure_service_user_and_group
from meltr.core.paths import (
    get_bundle_home_from_install_binary,
    get_install_root_from_binary,
    get_meltr_home,
    prefer_operator_binary,
)

app = typer.Typer(name="service", help="Systemd service management")
console = Console()

SERVICE_FILE = """[Unit]
Description=MELTr Synthetic Event Generator
After=network.target

[Service]
Type=simple
User={service_user}
Group={service_group}
WorkingDirectory={meltr_home}
ExecStart={meltr_bin} api start --foreground
Restart=on-failure
RestartSec=10s
TimeoutStartSec=90
LimitNOFILE=65536

# Environment
Environment="MELTR_HOME={meltr_home}"

# Optional: override application log path (default: <install_root>/logs/meltr.log)
# Environment="MELTR_LOG_FILE=/path/to/meltr.log"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meltr

[Install]
WantedBy=multi-user.target
"""


def _get_meltr_binary_path() -> Path:
    """Resolve path to the meltr binary (prefer product façade)."""
    opt_facade = Path("/opt/meltr/bin/meltr")
    if opt_facade.is_file():
        return opt_facade.resolve()

    found = shutil.which("meltr")
    if found:
        return prefer_operator_binary(Path(found))

    opt = Path("/opt")
    if opt.exists():
        for p in opt.iterdir():
            if not (p.is_dir() and p.name.lower() == "meltr"):
                continue
            facade = p / "bin" / "meltr"
            if facade.is_file():
                return facade.resolve()
            bundle_bin = p / "app" / "bin" / "meltr"
            if bundle_bin.is_file():
                return prefer_operator_binary(bundle_bin)
            venv_bin = p / ".venv" / "bin" / "meltr"
            if venv_bin.exists():
                return venv_bin.resolve()
            break

    for path in (
        "/usr/local/bin/meltr",
        "/usr/bin/meltr",
    ):
        if Path(path).exists():
            return prefer_operator_binary(Path(path))

    venv = os.environ.get("VIRTUAL_ENV", "")
    if venv:
        venv_bin = Path(venv) / "bin" / "meltr"
        if venv_bin.exists():
            return venv_bin.resolve()

    raise RuntimeError(
        "Could not find meltr binary. Install it system-wide or activate a virtual environment."
    )


def _check_root() -> None:
    """Check if running as root.

    Raises:
        typer.Exit: If not running as root
    """
    if os.geteuid() != 0:
        console.print("[red]Error: This command requires root privileges[/red]")
        console.print("[yellow]Hint: Use 'sudo meltr service <command>'[/yellow]")
        raise typer.Exit(code=1)


@app.command("install")
def service_install(
    meltr_home: str | None = typer.Option(None, "--home", help="MELTR_HOME directory"),
    meltr_bin: str | None = typer.Option(None, "--binary", help="Path to meltr binary"),
    user: str | None = typer.Option(
        None, "--user", "-u", help="User to run service as (default: meltr)"
    ),
    group: str | None = typer.Option(
        None, "--group", "-g", help="Group to run service as (default: same as user)"
    ),
    create_user: bool = typer.Option(
        True, "--create-user/--no-create-user", help="Create service user if it doesn't exist"
    ),
) -> None:
    """Install MELTr as a systemd service.

    Default ``MELTR_HOME`` matches the official bundle layout (``/opt/meltr`` when the
    binary lives under that tree). Override with ``--home`` for another state directory.
    Use --user meltr --no-create-user when the user already exists.
    Example:
        sudo meltr service install --user meltr --group meltr --binary /opt/meltr/bin/meltr
        sudo meltr service install --user meltr --group meltr --home /var/lib/meltr
    """
    _check_root()

    try:
        service_user = user or "meltr"
        service_group = group or service_user

        if meltr_bin:
            bin_path = prefer_operator_binary(Path(meltr_bin).expanduser())
        else:
            bin_path = _get_meltr_binary_path()

        if meltr_home:
            home_path = Path(meltr_home).expanduser().resolve()
        else:
            bundle_home = get_bundle_home_from_install_binary(bin_path)
            home_path = bundle_home if bundle_home is not None else get_meltr_home()

        if not bin_path.exists():
            console.print(f"[red]Error: MELTr binary not found at {bin_path}[/red]")
            raise typer.Exit(code=1)

        console.print("[green]Installing MELTr systemd service...[/green]")
        console.print(f"  Service user: {service_user}")
        console.print(f"  Service group: {service_group}")
        console.print(f"  MELTR_HOME: {home_path}")
        console.print(f"  ExecStart binary: {bin_path}")

        home_path.mkdir(parents=True, exist_ok=True)

        service_uid, service_gid = ensure_service_user_and_group(
            service_user,
            service_group,
            home_path,
            create_user,
            on_user_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_group_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_user_exists=lambda msg: console.print(f"[yellow]⚠ {msg}[/yellow]"),
            on_no_pwd_grp=lambda: console.print(
                "[yellow]⚠ pwd/grp modules not available, skipping user/group creation[/yellow]"
            ),
            on_useradd_missing=lambda: console.print(
                "[yellow]⚠ useradd/groupadd not found, skipping user/group creation[/yellow]"
            ),
        )

        if service_uid == 0 and service_gid == 0 and (pwd is None or grp is None):
            console.print("[yellow]⚠ pwd/grp modules not available, using root ownership[/yellow]")
            console.print("[yellow]⚠ Service may not start correctly[/yellow]")
        elif service_uid == 0 and service_gid == 0:
            console.print(
                f"[yellow]⚠ Could not get {service_user} user info - using root ownership[/yellow]"
            )
            console.print("[yellow]⚠ Service may not start correctly[/yellow]")

        # Set ownership to service user so service can write
        if service_uid is not None and (service_uid, service_gid) != (0, 0):
            os.chown(home_path, service_uid, service_gid)
            parent = home_path.parent
            if parent.exists():
                if parent.name.lower() in ("meltr",):
                    os.chown(parent, service_uid, service_gid)
                elif (
                    parent.name == "data"
                    and parent.parent.name.lower() in ("meltr",)
                    and parent.parent.exists()
                ):
                    os.chown(parent.parent, service_uid, service_gid)

        install_root = get_install_root_from_binary(bin_path)
        if install_root is not None:
            app_log_dir = install_root / "logs"
            app_log_dir.mkdir(parents=True, exist_ok=True)
            if service_uid is not None and (service_uid, service_gid) != (0, 0):
                os.chown(app_log_dir, service_uid, service_gid)
            try:
                profile_path, wrapper_path = write_operator_path_helpers(install_root)
                console.print(f"[green]✓ Wrote {profile_path}[/green]")
                console.print(f"[green]✓ Wrote {wrapper_path}[/green]")
            except FileNotFoundError as e:
                console.print(f"[yellow]⚠ Skipping PATH helpers: {e}[/yellow]")
            except OSError as e:
                console.print(f"[yellow]⚠ Could not write PATH helpers: {e}[/yellow]")
        else:
            log_dir = Path("/var/log/meltr")
            log_dir.mkdir(parents=True, exist_ok=True)
            if service_uid is not None and (service_uid, service_gid) != (0, 0):
                os.chown(log_dir, service_uid, service_gid)

        # Create service file (absolute ExecStart — never bare `meltr`)
        service_content = SERVICE_FILE.format(
            meltr_home=str(home_path),
            meltr_bin=str(bin_path),
            service_user=service_user,
            service_group=service_group,
        )

        service_file_path = Path("/etc/systemd/system/meltr.service")
        service_file_path.write_text(service_content)
        console.print(f"[green]✓ Created service file: {service_file_path}[/green]")

        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        console.print("[green]✓ Reloaded systemd daemon[/green]")

        console.print("\n[green]Service installed successfully![/green]")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("  sudo systemctl start meltr")
        console.print("  sudo systemctl enable meltr  # Start on boot")
        console.print("  sudo systemctl status meltr")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("uninstall")
def service_uninstall() -> None:
    """Uninstall MELTr systemd service.

    Removes only the systemd unit and reloads systemd. Data under MELTR_HOME,
    install-tree logs under ``<install_root>/logs``, and ``/var/log/meltr`` (if used)
    are left intentionally.
    """
    _check_root()

    try:
        # Stop and disable service
        subprocess.run(["systemctl", "stop", "meltr"], check=False)
        subprocess.run(["systemctl", "disable", "meltr"], check=False)

        # Remove service file
        service_file = Path("/etc/systemd/system/meltr.service")
        if service_file.exists():
            service_file.unlink()
            console.print("[green]✓ Removed service file[/green]")

        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        console.print("[green]✓ Service uninstalled[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("start")
def service_start() -> None:
    """Start the systemd service."""
    _check_root()

    try:
        subprocess.run(["systemctl", "start", "meltr"], check=True)
        console.print("[green]✓ Service started[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("stop")
def service_stop() -> None:
    """Stop the systemd service."""
    _check_root()

    try:
        subprocess.run(["systemctl", "stop", "meltr"], check=True)
        console.print("[green]✓ Service stopped[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("restart")
def service_restart() -> None:
    """Restart the systemd service."""
    _check_root()

    try:
        subprocess.run(["systemctl", "restart", "meltr"], check=True)
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
            ["systemctl", "status", "meltr", "--no-pager"],
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
