"""Initialization CLI command."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt

from logforge.core.config import Config, create_default_config
from logforge.core.paths import get_logforge_home, get_templates_path
from logforge.cli.user_utils import check_root, ensure_service_user_and_group

if TYPE_CHECKING:
    pass

console = Console()

app = typer.Typer(name="init", help="Initialize LogForge configuration")

DEFAULT_SERVICE_USER = "logmgr"


def _check_root_for_init() -> None:
    """Require root when --create-user is used."""
    if not check_root():
        console.print("[red]Error: Creating a service user requires root privileges.[/red]")
        console.print("[yellow]Hint: Use 'sudo logforge init ...' or run without --create-user[/yellow]")
        raise typer.Exit(code=1)


def init(
    directory: Optional[str] = None,
    interactive: bool = False,
    force: bool = False,
    user: Optional[str] = None,
    group: Optional[str] = None,
    create_user: bool = True,
) -> None:
    """Initialize LogForge configuration and directory structure.
    
    Creates a local LogForge installation directory (like Splunk/Cribl).
    By default creates ./logforge in the current directory. With --create-user
    and root, creates the service user/group (default: logmgr) and sets ownership.
    """
    if directory and directory is not None:
        home = Path(directory).expanduser().resolve()
    else:
        home = get_logforge_home()
    config_path = home / 'config.yaml'
    entities_path = home / 'entities.yaml'
    templates_path = get_templates_path(home)
    
    if config_path.exists() and not force:
        if not Confirm.ask(
            f"Configuration already exists at {config_path}. Overwrite?",
            default=False
        ):
            console.print("[yellow]Initialization cancelled[/yellow]")
            return
    
    if create_user:
        _check_root_for_init()
    
    service_user = user or DEFAULT_SERVICE_USER
    service_group = group or service_user
    service_uid, service_gid = None, None
    
    console.print(f"[green]Initializing LogForge in {home}[/green]")
    
    home.mkdir(parents=True, exist_ok=True)
    templates_path.mkdir(parents=True, exist_ok=True)
    (templates_path / 'default').mkdir(parents=True, exist_ok=True)
    (templates_path / 'custom').mkdir(parents=True, exist_ok=True)
    (home / 'outputs').mkdir(parents=True, exist_ok=True)
    
    if create_user:
        service_uid, service_gid = ensure_service_user_and_group(
            service_user,
            service_group,
            home,
            True,
            on_user_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_group_created=lambda msg: console.print(f"[green]✓ {msg}[/green]"),
            on_user_exists=lambda msg: console.print(f"[yellow]⚠ {msg}[/yellow]"),
            on_no_pwd_grp=lambda: console.print("[yellow]⚠ pwd/grp not available, skipping user/group creation[/yellow]"),
            on_useradd_missing=lambda: console.print("[yellow]⚠ useradd/groupadd not found, skipping user/group creation[/yellow]"),
        )
        if service_uid is not None and (service_uid, service_gid) != (0, 0):
            try:
                os.chown(home, service_uid, service_gid)
                for d in [templates_path, templates_path / 'default', templates_path / 'custom', home / 'outputs']:
                    if d.exists():
                        os.chown(d, service_uid, service_gid)
                if home.parent.name == 'logforge' and home.parent.exists():
                    os.chown(home.parent, service_uid, service_gid)
            except OSError as e:
                console.print(f"[yellow]⚠ Could not set ownership: {e}[/yellow]")
    
    # Create default config
    if interactive:
        config = _interactive_wizard(home)
    else:
        config = create_default_config(home)
    
    # Write config.yaml
    config_dict = config.model_dump(mode='json', exclude_none=True)
    with config_path.open('w', encoding='utf-8') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    # Set secure permissions (600)
    os.chmod(config_path, 0o600)
    
    # Create default entities.yaml if it doesn't exist
    if not entities_path.exists():
        _create_default_entities(home, entities_path)
        os.chmod(entities_path, 0o600)
    
    if service_uid is not None and (service_uid, service_gid) != (0, 0):
        try:
            os.chown(config_path, service_uid, service_gid)
            if entities_path.exists():
                os.chown(entities_path, service_uid, service_gid)
        except OSError:
            pass
    
    console.print(f"[green]✓ Configuration created at {config_path}[/green]")
    console.print(f"[green]✓ Directory structure created in {home}[/green]")
    
    if interactive:
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("  1. Review and customize config.yaml")
        console.print("  2. Add entities: logforge entities import <file>")
        console.print("  3. Install templates: logforge templates install <template-id>")
        console.print("  4. Start generators: logforge generators start <name>")


def _interactive_wizard(home: Path) -> 'Config':
    """Run interactive configuration wizard.
    
    Args:
        home: LOGFORGE_HOME path
        
    Returns:
        Config object with user selections
    """
    console.print("\n[bold]LogForge Configuration Wizard[/bold]\n")
    
    # Organization info
    org_name = Prompt.ask("Organization name", default="Acme Corporation")
    org_domain = Prompt.ask("Organization domain", default="acme.com")
    
    # API settings
    api_port = Prompt.ask("API server port", default="8080")
    try:
        api_port_int = int(api_port)
    except ValueError:
        api_port_int = 8080
        console.print("[yellow]Invalid port, using default 8080[/yellow]")
    
    # Template installation
    install_starter = Confirm.ask("Install starter template pack?", default=True)
    
    # Create config with user selections
    config = create_default_config(home)
    config.api.port = api_port_int
    
    # Note: Organization info will be in entities.yaml, not config.yaml
    # This is just for the wizard flow
    
    if install_starter:
        console.print("[yellow]Note: Template installation will be implemented in template commands[/yellow]")
    
    return config


def _create_default_entities(home: Path, entities_path: Path) -> None:
    """Create default entities.yaml from bundled sample or minimal fallback.
    
    Args:
        home: LOGFORGE_HOME path (used to resolve examples path when not in package).
        entities_path: Path to entities.yaml to write.
    """
    default_entities = None
    try:
        from importlib.resources import read_text
        content = read_text("logforge", "data/entities.sample.yaml", encoding="utf-8")
        default_entities = yaml.safe_load(content)
    except Exception:
        pass
    if default_entities is None:
        default_entities = {
            "organization": {
                "name": "Acme Corporation",
                "domain": "acme.com",
                "contacts": {
                    "admin": "admin@acme.com",
                    "security": "security@acme.com",
                },
            },
            "users": [],
            "devices": [],
            "services": [],
        }
    with entities_path.open("w", encoding="utf-8") as f:
        yaml.dump(default_entities, f, default_flow_style=False, sort_keys=False)

