"""Initialization CLI command."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt

from meltr.core.config import Config, create_default_config
from meltr.core.paths import get_logforge_home, get_templates_path
from meltr.cli.user_utils import check_root, ensure_service_user_and_group, service_user_and_group_exist

if TYPE_CHECKING:
    pass

console = Console()

app = typer.Typer(name="init", help="Initialize MELTr configuration")

DEFAULT_SERVICE_USER = "meltr"


def default_create_user() -> bool:
    """Default for --create-user when neither flag is passed: True only as root (typical service prep)."""
    try:
        return os.geteuid() == 0
    except (AttributeError, OSError):
        return False


def _check_root_for_init() -> None:
    """Require root when --create-user is used."""
    if not check_root():
        console.print("[red]Error: Creating a service user requires root privileges.[/red]")
        console.print(
            "[yellow]Hint: Use 'sudo meltr init ...', or 'meltr init --no-create-user' "
            "to initialize a user-writable MELTR_HOME without creating meltr.[/yellow]"
        )
        raise typer.Exit(code=1)


def init(
    directory: Optional[str] = None,
    interactive: bool = False,
    force: bool = False,
    user: Optional[str] = None,
    group: Optional[str] = None,
    create_user: Optional[bool] = None,
) -> None:
    """Initialize MELTr configuration and directory structure.

    Uses MELTR_HOME (default: ./.meltr or ./meltr when present, else
    ~/.meltr for interactive users or /opt/meltr for service accounts).
    Compat: LOGFORGE_HOME / .logforge / ./logforge still discovered.
    With --create-user and root, creates the service user/group (default: meltr)
    and sets ownership. If neither --create-user nor --no-create-user is passed,
    defaults to creating a service user only when running as root.
    """
    if create_user is None:
        create_user = default_create_user()
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

    service_user = user or DEFAULT_SERVICE_USER
    service_group = group or service_user
    # Require root only when we must create the user/group; if both exist, proceed without root
    if create_user and not service_user_and_group_exist(service_user, service_group):
        _check_root_for_init()
    service_uid, service_gid = None, None
    
    console.print(f"[green]Initializing MELTr in {home}[/green]")
    
    home.mkdir(parents=True, exist_ok=True)
    (home / 'run').mkdir(parents=True, exist_ok=True)
    (home / 'logs').mkdir(parents=True, exist_ok=True)
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
                for d in [
                    home / 'run',
                    home / 'logs',
                    templates_path,
                    templates_path / 'default',
                    templates_path / 'custom',
                    home / 'outputs',
                ]:
                    if d.exists():
                        os.chown(d, service_uid, service_gid)
                # Chown install root when home is under /opt/.../data or .../meltr|logforge
                parent = home.parent
                if parent.exists():
                    if parent.name.lower() in ('meltr', 'logforge'):
                        os.chown(parent, service_uid, service_gid)
                    elif (
                        parent.name == 'data'
                        and parent.parent.name.lower() in ('meltr', 'logforge')
                        and parent.parent.exists()
                    ):
                        os.chown(parent.parent, service_uid, service_gid)
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
    
    # Create default entities.yaml if missing; on --force replace (fixes broken/minimal registries)
    if not entities_path.exists() or force:
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
        console.print("  2. Add entities: meltr entities import <file>")
        console.print("  3. Install templates: meltr templates install <template-id>")
        console.print("  4. Start generators: meltr generators start <name>")


def _interactive_wizard(home: Path) -> 'Config':
    """Run interactive configuration wizard.
    
    Args:
        home: MELTR_HOME path
        
    Returns:
        Config object with user selections
    """
    console.print("\n[bold]MELTr Configuration Wizard[/bold]\n")
    
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


def _minimal_valid_entities() -> dict:
    """Smallest entity registry that passes validate_entities (for offline / missing bundle data)."""
    return {
        "organization": {
            "name": "Acme Corporation",
            "domain": "acme.com",
            "contacts": {
                "admin": "admin@acme.com",
            },
        },
        "users": [
            {
                "username": "admin",
                "email": "admin@acme.com",
                "full_name": "Administrator",
            },
        ],
        "devices": [
            {
                "hostname": "WORKSTATION-01",
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55",
            },
        ],
        "services": [
            {
                "name": "Example HTTP",
                "port": 80,
                "protocol": "HTTP",
            },
        ],
    }


def _load_bundled_sample_entities() -> Optional[dict]:
    """Load packaged entities.sample.yaml if present."""
    try:
        import meltr as _pkg

        path = Path(_pkg.__file__).resolve().parent / "data" / "entities.sample.yaml"
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content)
    except Exception:
        return None


def _create_default_entities(home: Path, entities_path: Path) -> None:
    """Create default entities.yaml from bundled sample or minimal fallback.
    
    Args:
        home: LOGFORGE_HOME path (used to resolve examples path when not in package).
        entities_path: Path to entities.yaml to write.
    """
    from meltr.entities.validator import validate_entities

    data = _load_bundled_sample_entities()
    if data is not None:
        try:
            validate_entities(data)
        except Exception:
            data = None
    if data is None:
        data = _minimal_valid_entities()
        validate_entities(data)
    with entities_path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

