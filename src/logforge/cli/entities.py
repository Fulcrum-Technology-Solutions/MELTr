"""Entity management CLI commands."""

from pathlib import Path
from typing import Literal, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from logforge.cli.api_client import APIClient, get_api_client
from logforge.core.paths import get_entities_path, validate_path_within_home
from logforge.entities.validator import validate_entities

app = typer.Typer(name="entities", help="Entity registry management")
console = Console()


@app.command("list")
def entities_list(
    entity_type: Optional[Literal["users", "devices", "services"]] = typer.Option(
        None, "--type", help="Filter by entity type"
    ),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """List entities in the registry."""
    client = get_api_client(api_url, api_key)
    
    try:
        if entity_type:
            # Get specific type
            response = client.get(f"/api/entities/{entity_type}")
            response.raise_for_status()
            data = response.json()
            
            # Display as table
            table = Table(title=f"{entity_type.capitalize()} Entities")
            if entity_type == "users":
                table.add_column("Username", style="cyan")
                table.add_column("Full Name", style="green")
                table.add_column("Email", style="yellow")
                table.add_column("Department", style="magenta")
                for entity in data["entities"]:
                    table.add_row(
                        entity.get("username", ""),
                        entity.get("full_name", ""),
                        entity.get("email", ""),
                        entity.get("department", ""),
                    )
            elif entity_type == "devices":
                table.add_column("Hostname", style="cyan")
                table.add_column("IP Address", style="green")
                table.add_column("OS Type", style="yellow")
                table.add_column("Owner", style="magenta")
                for entity in data["entities"]:
                    table.add_row(
                        entity.get("hostname", ""),
                        entity.get("ip_address", ""),
                        entity.get("os_type", ""),
                        entity.get("owner", ""),
                    )
            elif entity_type == "services":
                table.add_column("Name", style="cyan")
                table.add_column("Port", style="green")
                table.add_column("Protocol", style="yellow")
                table.add_column("Description", style="magenta")
                for entity in data["entities"]:
                    table.add_row(
                        entity.get("name", ""),
                        str(entity.get("port", "")),
                        entity.get("protocol", ""),
                        entity.get("description", ""),
                    )
            
            console.print(table)
            console.print(f"\n[dim]Showing page {data['page']} of {data['total_pages']} ({data['count']} total)[/dim]")
        else:
            # Get summary
            response = client.get("/api/entities")
            response.raise_for_status()
            data = response.json()
            
            console.print("\n[bold]Entity Registry Summary[/bold]\n")
            console.print(f"Organization: {data['organization']['name']} ({data['organization']['domain']})")
            console.print(f"Users: {data['users']}")
            console.print(f"Devices: {data['devices']}")
            console.print(f"Services: {data['services']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("show")
def entities_show(
    entity_type: Literal["user", "device", "service"],
    identifier: str = typer.Argument(..., help="Username, hostname, or service name"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Show details of a specific entity."""
    client = get_api_client(api_url, api_key)
    
    try:
        # Map entity_type to API type
        api_type = f"{entity_type}s"  # user -> users
        
        # Get all entities and find the one we want
        response = client.get(f"/api/entities/{api_type}?page_size=1000")
        response.raise_for_status()
        data = response.json()
        
        # Find entity
        entity = None
        if entity_type == "user":
            entity = next((e for e in data["entities"] if e.get("username", "").lower() == identifier.lower()), None)
        elif entity_type == "device":
            entity = next((e for e in data["entities"] if e.get("hostname", "") == identifier), None)
        elif entity_type == "service":
            entity = next((e for e in data["entities"] if e.get("name", "") == identifier), None)
        
        if not entity:
            console.print(f"[red]Error: {entity_type} '{identifier}' not found[/red]")
            raise typer.Exit(code=1)
        
        # Display entity details
        console.print(f"\n[bold]{entity_type.capitalize()}: {identifier}[/bold]\n")
        for key, value in sorted(entity.items()):
            if isinstance(value, dict):
                console.print(f"  [cyan]{key}:[/cyan]")
                for sub_key, sub_value in value.items():
                    console.print(f"    {sub_key}: {sub_value}")
            elif isinstance(value, list):
                console.print(f"  [cyan]{key}:[/cyan] {', '.join(str(v) for v in value)}")
            else:
                console.print(f"  [cyan]{key}:[/cyan] {value}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("validate")
def entities_validate(
    entities_path: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to entities.yaml file (default: LOGFORGE_HOME/entities.yaml)"),
    schema_path: Optional[Path] = typer.Option(None, "--schema", "-s", help="Path to entity.schema.json (default: auto-detect)"),
) -> None:
    """Validate entities.yaml file.
    
    Can validate files anywhere on the filesystem. Schema is auto-detected
    from common locations, or can be specified explicitly.
    """
    from logforge.core.paths import get_entities_path
    
    if entities_path is None:
        entities_path = get_entities_path()
    
    if not entities_path.exists():
        console.print(f"[red]Error: File not found: {entities_path}[/red]")
        raise typer.Exit(code=1)
    
    try:
        with entities_path.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        validate_entities(data, schema_path=schema_path)
        console.print(f"[green]✓ Entities file is valid: {entities_path}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Validation failed: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("import")
def entities_import(
    file_path: Path = typer.Argument(..., help="Path to entities YAML file to import"),
    merge: bool = typer.Option(False, "--merge", help="Merge with existing entities instead of replacing"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Import entities from YAML file."""
    from logforge.core.paths import get_logforge_home, get_entities_path
    from logforge.entities.storage import EntityStorage
    
    home = get_logforge_home()
    
    # Validate import file
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(code=1)
    
    # Load and validate import file (allow validation outside LOGFORGE_HOME)
    try:
        with file_path.open('r', encoding='utf-8') as f:
            import_data = yaml.safe_load(f)
        validate_entities(import_data, schema_path=None)  # Auto-detect schema
    except Exception as e:
        console.print(f"[red]Error: Invalid entities file: {e}[/red]")
        raise typer.Exit(code=1)
    
    # Try to use API if service is running
    client = get_api_client(api_url, api_key)
    is_healthy, _ = client.check_health()
    
    if is_healthy:
        # Use API to import (updates in-memory registry)
        try:
            response = client.post(
                "/api/entities/import",
                json=import_data,
                params={"merge": merge}
            )
            response.raise_for_status()
            data = response.json()
            
            console.print(f"[green]✓ {data['message']}[/green]")
            console.print(f"  Users: {data['users']}")
            console.print(f"  Devices: {data['devices']}")
            console.print(f"  Services: {data['services']}")
            return
        except Exception as e:
            console.print(f"[red]Error importing via API: {e}[/red]")
            console.print("[yellow]Falling back to direct file write...[/yellow]")
    
    # Fallback: Direct file write (service not running or API failed)
    console.print("[yellow]⚠ Service not running - importing directly to file[/yellow]")
    console.print("[dim]Note: Restart service or use 'logforge entities reload' to load changes[/dim]")
    
    # Load existing entities if merging (use strict=False to allow empty files)
    storage = EntityStorage()
    try:
        existing_data = storage.load(strict=False)
    except FileNotFoundError:
        existing_data = None
    
    if merge and existing_data:
        # Merge logic (simple merge, may have conflicts)
        console.print("[yellow]Merging with existing entities...[/yellow]")
        # TODO: Implement proper merge logic with conflict resolution
        merged_data = import_data.copy()
        merged_data['users'] = existing_data.get('users', []) + import_data.get('users', [])
        merged_data['devices'] = existing_data.get('devices', []) + import_data.get('devices', [])
        merged_data['services'] = existing_data.get('services', []) + import_data.get('services', [])
        # Re-validate merged data (auto-detect schema)
        validate_entities(merged_data, schema_path=None)
        storage.save(merged_data)
    else:
        # Replace
        storage.save(import_data)
    
    console.print(f"[green]✓ Entities imported successfully[/green]")
    console.print(f"  Users: {len(import_data.get('users', []))}")
    console.print(f"  Devices: {len(import_data.get('devices', []))}")
    console.print(f"  Services: {len(import_data.get('services', []))}")


@app.command("reload")
def entities_reload(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Reload entities from disk (requires running service)."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()
    
    try:
        response = client.post("/api/entities/reload")
        response.raise_for_status()
        data = response.json()
        
        console.print(f"[green]✓ {data['message']}[/green]")
        console.print(f"  Users: {data['users']}")
        console.print(f"  Devices: {data['devices']}")
        console.print(f"  Services: {data['services']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("export")
def entities_export(
    output_path: Path = typer.Argument(..., help="Path to save exported entities"),
) -> None:
    """Export entities to YAML file."""
    from logforge.entities.storage import EntityStorage
    
    storage = EntityStorage()
    
    try:
        data = storage.load()
        
        # Write to output file
        with output_path.open('w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        console.print(f"[green]✓ Entities exported to {output_path}[/green]")
    except FileNotFoundError:
        console.print("[red]Error: Entities file not found. Run 'logforge init' first.[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("add")
def entities_add(
    entity_type: Literal["user", "device", "service"] = typer.Argument(..., help="Type of entity to add"),
) -> None:
    """Interactively add a new entity."""
    from logforge.cli.entities_editor import (
        _create_user_interactive,
        _create_device_interactive,
        _create_service_interactive,
    )
    from logforge.entities.storage import EntityStorage
    
    storage = EntityStorage()
    
    try:
        data = storage.load(strict=False)
    except FileNotFoundError:
        from logforge.cli.entities_editor import _create_default_entities_structure
        data = _create_default_entities_structure()
    
    if entity_type == "user":
        new_entity = _create_user_interactive(data.get('users', []))
        if new_entity:
            data.setdefault('users', []).append(new_entity)
    elif entity_type == "device":
        new_entity = _create_device_interactive(data.get('devices', []))
        if new_entity:
            data.setdefault('devices', []).append(new_entity)
    elif entity_type == "service":
        new_entity = _create_service_interactive(data.get('services', []))
        if new_entity:
            data.setdefault('services', []).append(new_entity)
    
    if new_entity:
        try:
            from logforge.entities.validator import validate_entities
            validate_entities(data, schema_path=None)  # Auto-detect schema
            storage.save(data)
            console.print(f"[green]✓ {entity_type.capitalize()} added successfully[/green]")
        except ValueError as e:
            console.print(f"[red]Validation failed: {e}[/red]")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[red]Error saving: {e}[/red]")
            raise typer.Exit(code=1)


@app.command("edit")
def entities_edit() -> None:
    """Interactive entity registry editor."""
    from logforge.cli.entities_editor import entities_editor
    entities_editor()

