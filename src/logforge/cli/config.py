"""Configuration management CLI commands."""

import yaml
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from logforge.core.config import create_default_config, load_config
from logforge.core.paths import get_config_path, get_logforge_home
from logforge.cli.config_editor import config_editor

app = typer.Typer(name="config", help="Configuration management")
console = Console()


@app.command("show")
def config_show(
    path: Optional[str] = typer.Option(None, "--path", help="Show specific config section"),
    format: str = typer.Option("yaml", "--format", help="Output format: yaml or json"),
) -> None:
    """Show current configuration."""
    try:
        config = load_config()
        
        # Convert to dict for display
        config_dict = config.model_dump(mode='json')
        
        # Filter by path if specified
        if path:
            parts = path.split('.')
            for part in parts:
                if isinstance(config_dict, dict) and part in config_dict:
                    config_dict = config_dict[part]
                else:
                    console.print(f"[red]Error: Path '{path}' not found in config[/red]")
                    raise typer.Exit(code=1)
        
        # Display
        if format == "json":
            import json
            output = json.dumps(config_dict, indent=2)
            syntax = Syntax(output, "json", theme="monokai")
        else:
            output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
            syntax = Syntax(output, "yaml", theme="monokai")
        
        console.print(syntax)
        
    except FileNotFoundError:
        console.print("[red]Error: Config file not found. Run 'logforge init' first.[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("validate")
def config_validate(
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to config file"),
) -> None:
    """Validate configuration file."""
    try:
        if config_path:
            load_config(config_path, create_if_missing=False)
        else:
            load_config(create_if_missing=False)
        console.print("[green]✓ Configuration is valid[/green]")
    except FileNotFoundError:
        console.print("[yellow]⚠ Config file not found. Run 'logforge init' to create one.[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("edit")
def config_edit(
    section: Optional[str] = typer.Option(None, "--section", help="Edit specific section (outputs, generators, api, engine, logging)"),
    new: bool = typer.Option(False, "--new", help="Start with fresh default config instead of loading existing"),
) -> None:
    """Interactive configuration editor assistant."""
    config_editor(section=section, edit_existing=not new)


@app.command("reload")
def config_reload(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Reload configuration from disk and apply changes.
    
    Use this after editing config.yaml directly. Detects and applies:
    - Added generators (starts if enabled)
    - Removed generators (stops and removes)
    - Updated generators (restarts if was running)
    """
    from logforge.cli.api_client import get_api_client
    
    client = get_api_client(api_url, api_key)
    client.require_service_running()
    
    try:
        console.print("[cyan]Reloading configuration...[/cyan]")
        response = client.post("/api/config/reload", timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", {})
        added = results.get("added", [])
        removed = results.get("removed", [])
        updated = results.get("updated", [])
        errors = results.get("errors", [])
        
        if added:
            console.print(f"[green]✓ Started {len(added)} new generator(s): {', '.join(added)}[/green]")
        if removed:
            console.print(f"[yellow]✓ Stopped {len(removed)} removed generator(s): {', '.join(removed)}[/yellow]")
        if updated:
            console.print(f"[cyan]✓ Updated {len(updated)} generator(s): {', '.join(updated)}[/cyan]")
        if errors:
            console.print(f"[red]⚠ Errors during reload:[/red]")
            for error in errors:
                console.print(f"  [red]- {error}[/red]")
        
        if not (added or removed or updated or errors):
            console.print("[green]✓ Configuration reloaded (no generator changes)[/green]")
        else:
            console.print("[green]✓ Configuration reloaded successfully![/green]")
    except Exception as e:
        console.print(f"[red]Error reloading config: {e}[/red]")
        raise typer.Exit(code=1)

