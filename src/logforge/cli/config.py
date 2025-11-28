"""Configuration management CLI commands."""

import yaml
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from logforge.core.config import create_default_config, load_config
from logforge.core.paths import get_config_path, get_logforge_home

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
            load_config(config_path)
        else:
            load_config()
        console.print("[green]✓ Configuration is valid[/green]")
    except Exception as e:
        console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
        raise typer.Exit(code=1)

