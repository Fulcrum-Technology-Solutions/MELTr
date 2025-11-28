"""Systemd service management CLI commands."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(name="service", help="Systemd service management")
console = Console()

SERVICE_FILE = """[Unit]
Description=LogForge Synthetic Event Generator
After=network.target

[Service]
Type=simple
User=logforge
Group=logforge
WorkingDirectory={logforge_home}
ExecStart={logforge_bin} api start
Restart=on-failure
RestartSec=10s

# Environment
Environment="LOGFORGE_HOME={logforge_home}"

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
    # Try to find logforge in PATH
    logforge_path = shutil.which('logforge')
    if logforge_path:
        return Path(logforge_path)
    
    # Fall back to common locations
    for path in ['/usr/local/bin/logforge', '/usr/bin/logforge', '/opt/logforge/.venv/bin/logforge']:
        if Path(path).exists():
            return Path(path)
    
    # If in venv, use the venv's bin
    venv_bin = Path(os.environ.get('VIRTUAL_ENV', '')) / 'bin' / 'logforge'
    if venv_bin.exists():
        return venv_bin
    
    raise RuntimeError("Could not find logforge binary. Install it system-wide or activate virtual environment.")


def _get_logforge_home() -> Path:
    """Get LOGFORGE_HOME path.
    
    Returns:
        Path to LOGFORGE_HOME
    """
    env_home = os.getenv('LOGFORGE_HOME')
    if env_home:
        return Path(env_home).expanduser().resolve()
    
    # Default to /var/lib/logforge for systemd service
    return Path('/var/lib/logforge')


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
) -> None:
    """Install LogForge as a systemd service."""
    _check_root()
    
    try:
        # Determine paths
        if logforge_home:
            home_path = Path(logforge_home).expanduser().resolve()
        else:
            home_path = _get_logforge_home()
        
        if logforge_bin:
            bin_path = Path(logforge_bin).expanduser().resolve()
        else:
            bin_path = _get_logforge_binary_path()
        
        if not bin_path.exists():
            console.print(f"[red]Error: LogForge binary not found at {bin_path}[/red]")
            raise typer.Exit(code=1)
        
        console.print("[green]Installing LogForge systemd service...[/green]")
        
        # Create service user if it doesn't exist
        try:
            subprocess.run(
                ['useradd', '-r', '-s', '/bin/false', '-d', str(home_path), '-c', 'LogForge Service', 'logforge'],
                check=False,
                capture_output=True,
            )
            console.print("[green]✓ Created service user: logforge[/green]")
        except FileNotFoundError:
            console.print("[yellow]⚠ useradd not found, skipping user creation[/yellow]")
        except subprocess.CalledProcessError:
            # User might already exist, that's okay
            console.print("[yellow]⚠ Service user may already exist[/yellow]")
        
        # Create directories
        home_path.mkdir(parents=True, exist_ok=True)
        os.chown(home_path, 0, 0)  # root:root
        
        log_dir = Path('/var/log/logforge')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set ownership
        try:
            import pwd
            logforge_uid = pwd.getpwnam('logforge').pw_uid
            logforge_gid = pwd.getpwnam('logforge').pw_gid
            os.chown(log_dir, logforge_uid, logforge_gid)
        except (KeyError, ImportError):
            pass
        
        # Create service file
        service_content = SERVICE_FILE.format(
            logforge_home=str(home_path),
            logforge_bin=str(bin_path),
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
    """Uninstall LogForge systemd service."""
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
    """Show systemd service status."""
    _check_root()
    
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

