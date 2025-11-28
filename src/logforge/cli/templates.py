"""Template management CLI commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from logforge.cli.api_client import get_api_client
from logforge.core.paths import get_logforge_home, get_templates_path
from logforge.templates.loader import TemplateLoader
from logforge.templates.validator import validate_template
from logforge.templates.metadata import parse_metadata

app = typer.Typer(name="templates", help="Template management")
console = Console()


@app.command("list")
def templates_list(
    local_only: bool = typer.Option(False, "--local", help="Show only local templates"),
    remote_only: bool = typer.Option(False, "--remote", help="Show only remote templates"),
    custom_only: bool = typer.Option(False, "--custom-only", help="Show only custom templates"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """List available templates."""
    # TODO: Use API when available, fall back to direct loader for now
    from logforge.core.config import load_config
    
    try:
        config = load_config()
        loader = TemplateLoader(config)
        all_templates = loader.discover_templates()
        
        # Filter templates
        if custom_only:
            templates = {tid: t for tid, t in all_templates.items() if t.location == 'custom'}
        else:
            templates = all_templates
        
        # Display as table
        table = Table(title="Templates")
        table.add_column("ID", style="cyan")
        table.add_column("Location", style="green")
        table.add_column("Format", style="yellow")
        table.add_column("Vendor", style="magenta")
        table.add_column("Product", style="blue")
        
        for template_id, template_info in sorted(templates.items()):
            metadata = template_info.metadata
            table.add_row(
                template_id,
                template_info.location,
                metadata.format,
                template_info.vendor,
                template_info.product,
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(templates)} templates[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("info")
def templates_info(
    template_id: str = typer.Argument(..., help="Template ID"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Show detailed template information."""
    from logforge.core.config import load_config
    
    try:
        config = load_config()
        loader = TemplateLoader(config)
        template_info = loader.resolve_template(template_id)
        
        if not template_info:
            console.print(f"[red]Error: Template '{template_id}' not found[/red]")
            raise typer.Exit(code=1)
        
        metadata = template_info.metadata
        
        console.print(f"\n[bold]Template: {template_id}[/bold]\n")
        console.print(f"  [cyan]Location:[/cyan] {template_info.location}")
        console.print(f"  [cyan]Description:[/cyan] {metadata.description}")
        console.print(f"  [cyan]Format:[/cyan] {metadata.format}")
        console.print(f"  [cyan]Vendor:[/cyan] {template_info.vendor}")
        console.print(f"  [cyan]Product:[/cyan] {template_info.product}")
        console.print(f"  [cyan]Data Source:[/cyan] {template_info.data_source}")
        
        if metadata.frequency:
            console.print(f"  [cyan]Frequency:[/cyan] {metadata.frequency}")
        if metadata.is_generator:
            console.print(f"  [cyan]Generator:[/cyan] Yes")
            if metadata.base_frequency:
                console.print(f"  [cyan]Base Frequency:[/cyan] {metadata.base_frequency} events/hour")
        
        if metadata.documentation:
            doc = metadata.documentation
            if 'display' in doc:
                display = doc['display']
                if 'title' in display:
                    console.print(f"\n  [bold]Title:[/bold] {display['title']}")
                if 'tags' in display:
                    console.print(f"  [cyan]Tags:[/cyan] {', '.join(display['tags'])}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("validate")
def templates_validate(
    template_path: Optional[Path] = typer.Option(None, "--path", help="Path to template directory"),
) -> None:
    """Validate a template."""
    from logforge.core.paths import get_logforge_home
    
    home = get_logforge_home()
    
    if template_path is None:
        console.print("[red]Error: --path required[/red]")
        raise typer.Exit(code=1)
    
    # Validate path is within LOGFORGE_HOME
    if not template_path.is_absolute():
        template_path = home / template_path
    
    # Find template.j2 and metadata.yaml
    template_j2 = None
    metadata_yaml = None
    
    if template_path.is_file():
        if template_path.suffix == '.j2':
            template_j2 = template_path
            metadata_yaml = template_path.parent / f"{template_path.stem}.meta.yaml"
        elif template_path.name.endswith('.meta.yaml'):
            metadata_yaml = template_path
            template_j2 = template_path.parent / f"{template_path.stem.replace('.meta', '')}.j2"
    elif template_path.is_dir():
        # Look for .j2 and .meta.yaml files in directory
        for file in template_path.glob('*.j2'):
            template_j2 = file
            metadata_yaml = template_path / f"{file.stem}.meta.yaml"
            break
    
    if not template_j2 or not template_j2.exists():
        console.print(f"[red]Error: Template file not found: {template_j2}[/red]")
        raise typer.Exit(code=1)
    
    if not metadata_yaml or not metadata_yaml.exists():
        console.print(f"[red]Error: Metadata file not found: {metadata_yaml}[/red]")
        raise typer.Exit(code=1)
    
    # Validate
    result = validate_template(template_j2, metadata_yaml)
    
    if result.is_valid:
        console.print("[green]✓ Template is valid[/green]")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning: {warning}[/yellow]")
    else:
        console.print("[red]✗ Template validation failed[/red]")
        for error in result.errors:
            console.print(f"[red]  Error: {error}[/red]")
        for warning in result.warnings:
            console.print(f"[yellow]  Warning: {warning}[/yellow]")
        raise typer.Exit(code=1)


@app.command("customize")
def templates_customize(
    template_id: str = typer.Argument(..., help="Template ID to customize"),
) -> None:
    """Copy default template to custom for editing."""
    from logforge.core.config import load_config
    import shutil
    
    try:
        config = load_config()
        loader = TemplateLoader(config)
        
        # Find template in default
        template_info = loader.resolve_template(template_id)
        if not template_info:
            console.print(f"[red]Error: Template '{template_id}' not found[/red]")
            raise typer.Exit(code=1)
        
        if template_info.location == 'custom':
            console.print(f"[yellow]Template '{template_id}' is already a custom template[/yellow]")
            return
        
        # Copy to custom directory
        default_dir = template_info.template_path.parent
        custom_base = loader.custom_path
        
        # Recreate directory structure in custom
        parts = template_id.split('/')
        custom_dir = custom_base
        for part in parts[:-1]:  # All but template name
            custom_dir = custom_dir / part
        custom_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy files
        for file in default_dir.glob('*'):
            if file.is_file():
                shutil.copy2(file, custom_dir / file.name)
        
        console.print(f"[green]✓ Template copied to custom directory[/green]")
        console.print(f"  Location: {custom_dir}")
        console.print(f"  [dim]Edit files in custom/ to customize the template[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("revert")
def templates_revert(
    template_id: str = typer.Argument(..., help="Template ID to revert"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
) -> None:
    """Remove custom version, revert to using default."""
    from logforge.core.config import load_config
    from rich.prompt import Confirm
    import shutil
    
    try:
        config = load_config()
        loader = TemplateLoader(config)
        
        # Find template in custom
        template_info = loader.resolve_template(template_id)
        if not template_info or template_info.location != 'custom':
            console.print(f"[yellow]Template '{template_id}' is not a custom template[/yellow]")
            return
        
        if not force:
            if not Confirm.ask(f"Remove custom version of '{template_id}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        # Remove custom directory
        custom_dir = template_info.template_path.parent
        shutil.rmtree(custom_dir)
        
        console.print(f"[green]✓ Custom template removed[/green]")
        console.print(f"  Template will now use default version")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("search")
def templates_search(
    query: str = typer.Argument(..., help="Search query"),
    vendor: Optional[str] = typer.Option(None, "--vendor", help="Filter by vendor"),
    product: Optional[str] = typer.Option(None, "--product", help="Filter by product"),
) -> None:
    """Search templates (placeholder - will use community API)."""
    console.print("[yellow]Template search from community API not yet implemented[/yellow]")
    console.print(f"[dim]Searching for: {query}[/dim]")
    if vendor:
        console.print(f"[dim]Vendor filter: {vendor}[/dim]")
    if product:
        console.print(f"[dim]Product filter: {product}[/dim]")


@app.command("install")
def templates_install(
    template_id: str = typer.Argument(..., help="Template ID to install"),
) -> None:
    """Install template from community (placeholder)."""
    console.print("[yellow]Template installation from community API not yet implemented[/yellow]")
    console.print(f"[dim]Would install: {template_id}[/dim]")


@app.command("update")
def templates_update(
    template_id: Optional[str] = typer.Argument(None, help="Template ID to update (all if omitted)"),
) -> None:
    """Update templates from community (placeholder)."""
    console.print("[yellow]Template update from community API not yet implemented[/yellow]")
    if template_id:
        console.print(f"[dim]Would update: {template_id}[/dim]")
    else:
        console.print("[dim]Would update all templates[/dim]")


@app.command("diff")
def templates_diff(
    template_id: str = typer.Argument(..., help="Template ID to diff"),
) -> None:
    """Show differences between custom and default versions."""
    console.print("[yellow]Template diff not yet implemented[/yellow]")
    console.print(f"[dim]Would show diff for: {template_id}[/dim]")


@app.command("merge")
def templates_merge(
    template_id: str = typer.Argument(..., help="Template ID to merge"),
) -> None:
    """Merge default changes into custom version."""
    console.print("[yellow]Template merge not yet implemented[/yellow]")
    console.print(f"[dim]Would merge: {template_id}[/dim]")


@app.command("create")
def templates_create(
    template_path: str = typer.Argument(..., help="Template path (e.g., custom/acme/myapp)"),
) -> None:
    """Create a new custom template (interactive wizard)."""
    console.print("[yellow]Template creation wizard not yet implemented[/yellow]")
    console.print(f"[dim]Would create template at: {template_path}[/dim]")
