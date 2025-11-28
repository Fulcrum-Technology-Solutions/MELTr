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
    # Windows or other platforms without pwd/grp
    grp = None
    pwd = None

import typer
from rich.console import Console

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
    
    Detects installation directory from binary location (like Splunk/Cribl).
    Defaults to installation directory/logforge or /opt/logforge/logforge.
    
    Returns:
        Path to LOGFORGE_HOME
    """
    env_home = os.getenv('LOGFORGE_HOME')
    if env_home:
        return Path(env_home).expanduser().resolve()
    
    # Try to detect from binary location
    try:
        bin_path = _get_logforge_binary_path()
        # If binary is in /opt/logforge/.venv/bin/logforge, use /opt/logforge/logforge
        # If binary is in /usr/local/bin/logforge, use /opt/logforge/logforge
        # If binary is in /usr/bin/logforge, use /opt/logforge/logforge
        if '/opt/logforge' in str(bin_path):
            # Installation is in /opt/logforge
            install_dir = Path('/opt/logforge')
            home = install_dir / 'logforge'
            return home.resolve()
        elif bin_path.parent.parent.name == 'logforge':
            # Binary is in something like /path/to/logforge/.venv/bin/logforge
            install_dir = bin_path.parent.parent
            home = install_dir / 'logforge'
            return home.resolve()
    except Exception:
        pass
    
    # Fallback: try /opt/logforge/logforge (common installation location)
    opt_home = Path('/opt/logforge/logforge')
    if opt_home.parent.exists():
        return opt_home.resolve()
    
    # Last resort: /var/lib/logforge
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
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User to run service as (default: logforge)"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Group to run service as (default: same as user)"),
    create_user: bool = typer.Option(True, "--create-user/--no-create-user", help="Create service user if it doesn't exist"),
) -> None:
    """Install LogForge as a systemd service.
    
    Similar to Splunk/Cribl installation, allows specifying the service user.
    Example:
        sudo logforge service install --user logmgr --group logmgr --home /opt/logforge/logforge
    """
    _check_root()
    
    try:
        # Determine service user and group
        service_user = user or 'logforge'
        service_group = group or service_user
        
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
        
        console.print(f"[green]Installing LogForge systemd service...[/green]")
        console.print(f"  Service user: {service_user}")
        console.print(f"  Service group: {service_group}")
        console.print(f"  LOGFORGE_HOME: {home_path}")
        
        # Create directories first
        home_path.mkdir(parents=True, exist_ok=True)
        
        # Create service user if requested and it doesn't exist
        service_uid = None
        service_gid = None
        
        if create_user:
            if pwd is None or grp is None:
                console.print("[yellow]⚠ pwd/grp modules not available, skipping user/group creation[/yellow]")
            else:
                try:
                    # Check if user exists
                    try:
                        pwd.getpwnam(service_user)
                        console.print(f"[yellow]⚠ User {service_user} already exists[/yellow]")
                    except KeyError:
                        # User doesn't exist, create it
                        try:
                            subprocess.run(
                                ['useradd', '-r', '-s', '/bin/false', '-d', str(home_path), 
                                 '-c', 'LogForge Service', service_user],
                                check=True,
                                capture_output=True,
                            )
                            console.print(f"[green]✓ Created service user: {service_user}[/green]")
                        except subprocess.CalledProcessError as e:
                            console.print(f"[yellow]⚠ Could not create user {service_user}: {e}[/yellow]")
                    
                    # Check if group exists
                    try:
                        grp.getgrnam(service_group)
                    except KeyError:
                        # Group doesn't exist, create it
                        try:
                            subprocess.run(
                                ['groupadd', '-r', service_group],
                                check=True,
                                capture_output=True,
                            )
                            console.print(f"[green]✓ Created service group: {service_group}[/green]")
                        except subprocess.CalledProcessError:
                            # Group might already exist or creation failed, that's okay
                            pass
                            
                except FileNotFoundError:
                    console.print("[yellow]⚠ useradd/groupadd not found, skipping user/group creation[/yellow]")
        
        # Get service user UID/GID
        if pwd is None or grp is None:
            console.print("[yellow]⚠ pwd/grp modules not available, using root ownership[/yellow]")
            console.print("[yellow]⚠ Service may not start correctly[/yellow]")
            service_uid = 0
            service_gid = 0
        else:
            try:
                service_uid = pwd.getpwnam(service_user).pw_uid
                try:
                    service_gid = grp.getgrnam(service_group).gr_gid
                except KeyError:
                    # If group doesn't exist, use user's primary group
                    service_gid = pwd.getpwnam(service_user).pw_gid
            except KeyError as e:
                console.print(f"[yellow]⚠ Could not get {service_user} user info: {e}[/yellow]")
                console.print("[yellow]⚠ Using root ownership - service may not start correctly[/yellow]")
                service_uid = 0
                service_gid = 0
        
        # Set ownership to service user so service can write
        if service_uid is not None:
            os.chown(home_path, service_uid, service_gid)
            # Also set ownership on parent if it's the installation directory
            if home_path.parent.name == 'logforge' and home_path.parent.exists():
                os.chown(home_path.parent, service_uid, service_gid)
        
        log_dir = Path('/var/log/logforge')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set ownership on log directory
        if service_uid is not None:
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

