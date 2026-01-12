"""Configuration management CLI commands."""

import yaml
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from logforge.core.config import create_default_config, load_config, save_config
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


def _quick_add_generator(
    template: str,
    name: Optional[str],
    outputs_str: Optional[str],
    timezone: Optional[str],
) -> None:
    """Quick-add a generator via CLI arguments."""
    from logforge.core.config import GeneratorConfig
    
    try:
        config = load_config()
    except FileNotFoundError:
        console.print("[red]Error: Config file not found. Run 'logforge init' first.[/red]")
        raise typer.Exit(code=1)
    
    # Generate name if not provided
    if not name:
        # Use template ID as base for name
        name_parts = template.split('/')
        name = f"{name_parts[-2]}-{name_parts[-1]}" if len(name_parts) >= 2 else template.replace('/', '-')
        # Ensure unique name
        existing_names = {g.name for g in config.generators}
        base_name = name
        counter = 1
        while name in existing_names:
            name = f"{base_name}-{counter}"
            counter += 1
    
    # Validate template exists
    try:
        from logforge.templates.loader import TemplateLoader
        loader = TemplateLoader(config)
        templates = loader.discover_templates()
        if template not in templates:
            console.print(f"[yellow]Warning: Template '{template}' not found. Will be validated on start.[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not validate template: {e}[/yellow]")
    
    # Parse outputs
    if not outputs_str:
        if not config.outputs.definitions:
            console.print("[red]Error: No outputs configured. Please add outputs first.[/red]")
            raise typer.Exit(code=1)
        # Use first output as default
        selected_outputs = [config.outputs.definitions[0].name]
        console.print(f"[yellow]No outputs specified, using first output: {selected_outputs[0]}[/yellow]")
    else:
        selected_outputs = [o.strip() for o in outputs_str.split(",") if o.strip()]
        # Validate outputs exist
        available_outputs = {o.name for o in config.outputs.definitions}
        invalid_outputs = set(selected_outputs) - available_outputs
        if invalid_outputs:
            console.print(f"[red]Error: Invalid output(s): {', '.join(invalid_outputs)}[/red]")
            console.print(f"[yellow]Available outputs: {', '.join(available_outputs)}[/yellow]")
            raise typer.Exit(code=1)
    
    # Check if generator name already exists
    if any(g.name == name for g in config.generators):
        console.print(f"[red]Error: Generator '{name}' already exists[/red]")
        raise typer.Exit(code=1)
    
    # Create generator
    generator = GeneratorConfig(
        name=name,
        template=template,
        enabled=True,
        outputs=selected_outputs,
        timezone=timezone,
    )
    
    config.generators.append(generator)
    
    # Save config
    try:
        save_config(config)
        console.print(f"[green]✓ Added generator: {name}[/green]")
        console.print(f"  Template: {template}")
        console.print(f"  Outputs: {', '.join(selected_outputs)}")
        if timezone:
            console.print(f"  Timezone: {timezone}")
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        raise typer.Exit(code=1)


def _quick_edit_generator(
    name: str,
    enable: Optional[bool],
    outputs_str: Optional[str],
    timezone: Optional[str],
) -> None:
    """Quick-edit a generator via CLI arguments."""
    
    try:
        config = load_config()
    except FileNotFoundError:
        console.print("[red]Error: Config file not found. Run 'logforge init' first.[/red]")
        raise typer.Exit(code=1)
    
    # Find generator
    generator = None
    for gen in config.generators:
        if gen.name == name:
            generator = gen
            break
    
    if not generator:
        console.print(f"[red]Error: Generator '{name}' not found[/red]")
        available = [g.name for g in config.generators]
        if available:
            console.print(f"[yellow]Available generators: {', '.join(available)}[/yellow]")
        raise typer.Exit(code=1)
    
    changes = []
    
    # Update enabled status
    if enable is not None:
        generator.enabled = enable
        changes.append(f"enabled={enable}")
    
    # Update outputs
    if outputs_str is not None:
        selected_outputs = [o.strip() for o in outputs_str.split(",") if o.strip()]
        # Validate outputs exist
        available_outputs = {o.name for o in config.outputs.definitions}
        invalid_outputs = set(selected_outputs) - available_outputs
        if invalid_outputs:
            console.print(f"[red]Error: Invalid output(s): {', '.join(invalid_outputs)}[/red]")
            console.print(f"[yellow]Available outputs: {', '.join(available_outputs)}[/yellow]")
            raise typer.Exit(code=1)
        generator.outputs = selected_outputs
        changes.append(f"outputs={','.join(selected_outputs)}")
    
    # Update timezone
    if timezone is not None:
        generator.timezone = timezone.strip() if timezone.strip() else None
        changes.append(f"timezone={generator.timezone or '(none)'}")
    
    if not changes:
        console.print("[yellow]No changes specified. Use --enable/--disable, --outputs, or --timezone[/yellow]")
        return
    
    # Save config
    try:
        save_config(config)
        console.print(f"[green]✓ Updated generator: {name}[/green]")
        for change in changes:
            console.print(f"  {change}")
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("edit")
def config_edit(
    section: Optional[str] = typer.Option(None, "--section", help="Edit specific section (outputs, generators, api, engine, logging)"),
    new: bool = typer.Option(False, "--new", help="Start with fresh default config instead of loading existing"),
    add_generator: Optional[str] = typer.Option(None, "--add-generator", "--add", help="Quick-add generator: template ID (e.g., 'microsoft/azure/signin')"),
    generator_name: Optional[str] = typer.Option(None, "--name", help="Generator name (used with --add-generator or --edit-generator)"),
    outputs: Optional[str] = typer.Option(None, "--outputs", help="Comma-separated output names (used with --add-generator or --edit-generator)"),
    edit_generator: Optional[str] = typer.Option(None, "--edit-generator", "--edit-gen", help="Quick-edit generator by name"),
    enable: Optional[bool] = typer.Option(None, "--enable/--disable", help="Enable/disable generator (used with --edit-generator)"),
    timezone: Optional[str] = typer.Option(None, "--timezone", help="Timezone override (used with --add-generator or --edit-generator)"),
) -> None:
    """Interactive configuration editor assistant.
    
    Quick operations:
      --add-generator <template> --name <name> --outputs <outputs>  Quick-add generator
      --edit-generator <name> --enable/--disable                     Quick-toggle generator
      --edit-generator <name> --outputs <outputs>                    Quick-update outputs
    """
    # Quick-add generator mode
    if add_generator:
        _quick_add_generator(
            template=add_generator,
            name=generator_name,
            outputs_str=outputs,
            timezone=timezone,
        )
        return
    
    # Quick-edit generator mode
    if edit_generator:
        _quick_edit_generator(
            name=edit_generator,
            enable=enable,
            outputs_str=outputs,
            timezone=timezone,
        )
        return
    
    # Interactive mode (existing behavior)
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

