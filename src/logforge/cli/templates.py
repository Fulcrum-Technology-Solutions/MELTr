"""Template management CLI commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn
from logforge.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
    CommunityAPIRateLimitError,
)
from logforge.community.package import (
    download_and_install_vendor,
    download_and_install_product,
    get_local_collection_version,
    PackageError,
)
from logforge.community.version import compare_versions, format_version_status
from logforge.core.config import load_config
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
    show_remote: bool = typer.Option(False, "--show-remote", help="Include remote templates with installed status"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
) -> None:
    """List available templates (local and/or remote)."""
    from logforge.core.config import load_config
    
    try:
        config = load_config()
        
        # Get local templates
        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()
        local_template_ids = set(local_templates.keys())
        
        # Filter local templates
        if custom_only:
            templates_to_show = {tid: t for tid, t in local_templates.items() if t.location == 'custom'}
        else:
            templates_to_show = local_templates
        
        # Get remote templates if requested
        remote_templates = {}
        if remote_only or show_remote:
            if api_url is None:
                api_url = config.templates.community_api_url
            
            try:
                client = CommunityAPIClient(base_url=api_url)
                result = client.search_templates(page=1, page_size=100)
                
                # Build remote template dict
                for vendor_data in result.get('vendors', []):
                    for product_data in vendor_data.get('products', []):
                        for ds_data in product_data.get('data_sources', []):
                            for template in ds_data.get('templates', []):
                                template_id = template.get('id')
                                if template_id:
                                    remote_templates[template_id] = {
                                        'name': template.get('name', template_id),
                                        'vendor': vendor_data.get('id'),
                                        'product': product_data.get('product_id'),
                                        'format': template.get('format', 'N/A'),
                                    }
            except Exception as e:
                if remote_only:
                    console.print(f"[red]Error fetching remote templates: {e}[/red]")
                    raise typer.Exit(code=1)
                console.print(f"[yellow]Warning: Could not fetch remote templates: {e}[/yellow]")
        
        # Create unified template info structure
        unified_templates = {}
        
        # Add local templates
        for tid, template_info in templates_to_show.items():
            unified_templates[tid] = {
                'format': template_info.metadata.format,
                'vendor': template_info.vendor,
                'product': template_info.product,
                'location': template_info.location,
            }
        
        # Add remote templates based on options
        if remote_only:
            unified_templates = {}
            for tid, remote_info in remote_templates.items():
                unified_templates[tid] = {
                    'format': remote_info['format'],
                    'vendor': remote_info['vendor'],
                    'product': remote_info['product'],
                    'location': 'remote',
                }
        elif show_remote:
            # Merge remote templates (only add if not already in local)
            for tid, remote_info in remote_templates.items():
                if tid not in unified_templates:
                    unified_templates[tid] = {
                        'format': remote_info['format'],
                        'vendor': remote_info['vendor'],
                        'product': remote_info['product'],
                        'location': 'remote',
                    }
        
        # Display as table
        table = Table(title="Templates")
        table.add_column("ID", style="cyan")
        table.add_column("Installed", style="green")
        table.add_column("Location", style="dim")
        table.add_column("Format", style="yellow")
        table.add_column("Vendor", style="magenta")
        table.add_column("Product", style="blue")
        
        for template_id in sorted(unified_templates.keys()):
            template_info = unified_templates[template_id]
            
            # Determine installed status
            is_installed = template_id in local_template_ids
            installed_mark = "[green]✓[/green]" if is_installed else "[dim]-[/dim]"
            
            table.add_row(
                template_id,
                installed_mark,
                template_info['location'],
                template_info['format'],
                template_info['vendor'],
                template_info['product'],
            )
        
        console.print(table)
        
        local_count = len([t for t in unified_templates.keys() if t in local_template_ids])
        remote_count = len([t for t in unified_templates.keys() if t not in local_template_ids])
        
        summary = f"\n[dim]Total: {len(unified_templates)} templates"
        if show_remote or remote_only:
            summary += f" ({local_count} installed, {remote_count} available remotely)"
        summary += "[/dim]"
        console.print(summary)
        
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
    template_path: Optional[Path] = typer.Option(None, "--path", "--file", help="Path to template file or directory"),
) -> None:
    """Validate a template."""
    from logforge.core.paths import get_logforge_home
    
    if template_path is None:
        console.print("[red]Error: --path or --file required[/red]")
        console.print("[dim]Example: logforge templates validate --file /path/to/template.j2[/dim]")
        console.print("[dim]Example: logforge templates validate --path /path/to/template/directory[/dim]")
        raise typer.Exit(code=1)
    
    # Convert to Path if it's a string
    if isinstance(template_path, str):
        template_path = Path(template_path)
    
    # Resolve path - try as-is first, then relative to current directory, then relative to LOGFORGE_HOME
    resolved_path = None
    if template_path.is_absolute() and template_path.exists():
        resolved_path = template_path
    elif template_path.exists():
        resolved_path = template_path.resolve()
    else:
        # Try relative to current directory
        current_dir_path = Path.cwd() / template_path
        if current_dir_path.exists():
            resolved_path = current_dir_path.resolve()
        else:
            # Try relative to LOGFORGE_HOME
            home = get_logforge_home()
            home_path = home / template_path
            if home_path.exists():
                resolved_path = home_path.resolve()
            else:
                # Use the original path (will show error below)
                resolved_path = template_path.resolve() if template_path.is_absolute() else Path.cwd() / template_path
    
    # Find template.j2 and metadata.yaml
    template_j2 = None
    metadata_yaml = None
    
    if resolved_path.is_file():
        if resolved_path.suffix == '.j2':
            template_j2 = resolved_path
            metadata_yaml = resolved_path.parent / f"{resolved_path.stem}.meta.yaml"
        elif resolved_path.name.endswith('.meta.yaml'):
            metadata_yaml = resolved_path
            template_j2 = resolved_path.parent / f"{resolved_path.stem.replace('.meta', '')}.j2"
        else:
            console.print(f"[red]Error: File must be a .j2 template or .meta.yaml metadata file[/red]")
            console.print(f"[dim]Provided: {resolved_path}[/dim]")
            raise typer.Exit(code=1)
    elif resolved_path.is_dir():
        # Look for .j2 and .meta.yaml files in directory
        for file in resolved_path.glob('*.j2'):
            template_j2 = file
            metadata_yaml = resolved_path / f"{file.stem}.meta.yaml"
            break
    else:
        console.print(f"[red]Error: Path does not exist: {resolved_path}[/red]")
        raise typer.Exit(code=1)
    
    if not template_j2:
        console.print(f"[red]Error: Template file (.j2) not found in: {resolved_path}[/red]")
        raise typer.Exit(code=1)
    
    if not template_j2.exists():
        console.print(f"[red]Error: Template file not found: {template_j2}[/red]")
        raise typer.Exit(code=1)
    
    if not metadata_yaml:
        console.print(f"[red]Error: Metadata file (.meta.yaml) not found for: {template_j2}[/red]")
        raise typer.Exit(code=1)
    
    if not metadata_yaml.exists():
        console.print(f"[red]Error: Metadata file not found: {metadata_yaml}[/red]")
        console.print(f"[dim]Expected: {metadata_yaml}[/dim]")
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
    query: Optional[str] = typer.Argument(None, help="Search query (omit to browse all templates)"),
    vendor: Optional[str] = typer.Option(None, "--vendor", help="Filter by vendor"),
    product: Optional[str] = typer.Option(None, "--product", help="Filter by product"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
    page: int = typer.Option(1, "--page", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", help="Results per page"),
) -> None:
    """Search or browse templates from community registry."""
    try:
        # Get API URL from config or parameter
        if api_url is None:
            config = load_config()
            api_url = config.templates.community_api_url
        
        # Create API client
        client = CommunityAPIClient(base_url=api_url)
        
        # Display search/filter info
        if query:
            console.print(f"[dim]Searching for: {query}[/dim]")
        elif vendor or product:
            filters = []
            if vendor:
                filters.append(f"vendor={vendor}")
            if product:
                filters.append(f"product={product}")
            console.print(f"[dim]Filtering: {', '.join(filters)}[/dim]")
        else:
            console.print(f"[dim]Browsing all templates (page {page})[/dim]")
        
        # Search/browse templates
        result = client.search_templates(
            query=query,
            vendor_id=vendor,
            product_id=product,
            page=page,
            page_size=page_size,
        )
        
        vendors = result.get('vendors', [])
        total = result.get('total', 0)
        
        if not vendors:
            console.print("[yellow]No templates found[/yellow]")
            return
        
        # Display results
        console.print(f"\n[bold]Found {total} vendor(s)[/bold]\n")
        
        for vendor_data in vendors:
            vendor_id = vendor_data.get('id', 'unknown')
            vendor_name = vendor_data.get('vendor', vendor_id)
            
            console.print(f"[bold cyan]{vendor_name}[/bold cyan] ({vendor_id})")
            
            for product_data in vendor_data.get('products', []):
                product_id = product_data.get('product_id', 'unknown')
                product_name = product_data.get('product', product_id)
                collection_version = product_data.get('collection_version', 'N/A')
                
                console.print(f"  [green]└─[/green] {product_name} (v{collection_version})")
                
                for data_source_data in product_data.get('data_sources', []):
                    ds_id = data_source_data.get('data_source_id', 'unknown')
                    ds_name = data_source_data.get('name', ds_id)
                    
                    templates = data_source_data.get('templates', [])
                    if templates:
                        console.print(f"      [yellow]└─[/yellow] {ds_name} ({len(templates)} templates)")
                        
                        # Show first few templates
                        for template in templates[:3]:
                            template_id = template.get('event_type_id', 'unknown')
                            template_name = template.get('name', template_id)
                            console.print(f"          • {template_name}")
                        
                        if len(templates) > 3:
                            console.print(f"          ... and {len(templates) - 3} more")
            
            console.print()
        
        if total > page_size:
            total_pages = (total + page_size - 1) // page_size
            console.print(f"[dim]Showing page {page} of {total_pages}[/dim]")
            if page < total_pages:
                console.print(f"[dim]Use --page {page + 1} to see more results[/dim]")
    
    except CommunityAPIRateLimitError as e:
        console.print(f"[red]Rate limit exceeded: {e}[/red]")
        raise typer.Exit(code=1)
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", exc_info=True)
        raise typer.Exit(code=1)


@app.command("browse")
def templates_browse(
    vendor: Optional[str] = typer.Option(None, "--vendor", help="Browse templates for specific vendor"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
    page: int = typer.Option(1, "--page", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", help="Results per page"),
) -> None:
    """Browse community templates hierarchically (vendors → products → templates)."""
    try:
        # Get API URL from config or parameter
        if api_url is None:
            config = load_config()
            api_url = config.templates.community_api_url
        
        client = CommunityAPIClient(base_url=api_url)
        
        if vendor:
            # Show vendor detail with all products using search_templates for full hierarchy
            console.print(f"[dim]Browsing vendor: {vendor}[/dim]\n")
            
            try:
                # Use search with vendor filter to get full hierarchy
                result = client.search_templates(vendor_id=vendor, page=1, page_size=100)
                vendors = result.get('vendors', [])
                
                if not vendors:
                    console.print(f"[yellow]Vendor '{vendor}' not found or has no templates[/yellow]")
                    return
                
                vendor_data = vendors[0]  # Should only be one vendor
                vendor_id = vendor_data.get('id', vendor)
                vendor_name = vendor_data.get('vendor', vendor)
                
                console.print(f"[bold cyan]{vendor_name}[/bold cyan] ({vendor_id})\n")
                
                products = vendor_data.get('products', [])
                if not products:
                    console.print("[yellow]No products found for this vendor[/yellow]")
                    return
                
                for product_data in products:
                    product_id = product_data.get('product_id', 'unknown')
                    product_name = product_data.get('product', product_id)
                    collection_version = product_data.get('collection_version', 'N/A')
                    
                    console.print(f"  [green]└─[/green] {product_name} (v{collection_version})")
                    
                    data_sources = product_data.get('data_sources', [])
                    for ds_data in data_sources:
                        ds_id = ds_data.get('data_source_id', 'unknown')
                        ds_name = ds_data.get('name', ds_id)
                        templates = ds_data.get('templates', [])
                        
                        if templates:
                            console.print(f"      [yellow]└─[/yellow] {ds_name} ({len(templates)} templates)")
                            for template in templates[:5]:
                                template_name = template.get('name', template.get('event_type_id', 'unknown'))
                                console.print(f"          • {template_name}")
                            if len(templates) > 5:
                                console.print(f"          ... and {len(templates) - 5} more")
                    
                    console.print()
                        
            except CommunityAPINotFoundError:
                console.print(f"[red]Error: Vendor '{vendor}' not found[/red]")
                raise typer.Exit(code=1)
        else:
            # List all vendors using search_templates to get full hierarchy with product counts
            console.print("[dim]Browsing all vendors[/dim]\n")
            
            try:
                result = client.search_templates(page=1, page_size=100)
                vendors = result.get('vendors', [])
                
                if not vendors:
                    console.print("[yellow]No vendors found[/yellow]")
                    return
                
                console.print(f"[bold]Available Vendors ({len(vendors)}):[/bold]\n")
                
                for vendor_data in vendors:
                    vendor_id = vendor_data.get('id', 'unknown')
                    vendor_name = vendor_data.get('vendor', vendor_id)
                    vendor_desc = vendor_data.get('description', '')
                    products = vendor_data.get('products', [])
                    products_count = len(products)
                    
                    console.print(f"[cyan]{vendor_name}[/cyan] ([dim]{vendor_id}[/dim])")
                    if vendor_desc:
                        console.print(f"  [dim]{vendor_desc[:80]}{'...' if len(vendor_desc) > 80 else ''}[/dim]")
                    console.print(f"  [green]{products_count} product(s) available[/green]")
                    console.print(f"  [dim]Use: logforge templates browse --vendor {vendor_id}[/dim]\n")
            except Exception as e:
                console.print(f"[yellow]Warning: Using fallback vendor list[/yellow]")
                # Fallback to basic vendor list if search fails
                vendors = client.get_vendors()
                for vendor_data in vendors:
                    vendor_id = vendor_data.get('id', 'unknown')
                    vendor_name = vendor_data.get('vendor', vendor_id)
                    console.print(f"[cyan]{vendor_name}[/cyan] ([dim]{vendor_id}[/dim])")
                    console.print(f"  [dim]Use: logforge templates browse --vendor {vendor_id}[/dim]\n")
    
    except CommunityAPIRateLimitError as e:
        console.print(f"[red]Rate limit exceeded: {e}[/red]")
        raise typer.Exit(code=1)
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", exc_info=True)
        raise typer.Exit(code=1)


@app.command("install")
def templates_install(
    vendor_or_product: Optional[str] = typer.Argument(None, help="Vendor ID (e.g., 'microsoft') or Product ID (e.g., 'microsoft/windows')"),
    vendor: bool = typer.Option(False, "--vendor", help="Install all products from vendor"),
    product: bool = typer.Option(False, "--product", help="Install specific product (use vendor/product format)"),
    list_vendors: bool = typer.Option(False, "--list-vendors", help="List available vendors to install"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing installation"),
    local_file: Optional[Path] = typer.Option(None, "--local-file", help="Install from local .forge file"),
) -> None:
    """Install template packages from community registry or local package.
    
    Installation levels:
      - Vendor: Install all products for a vendor
        Example: logforge templates install microsoft --vendor
      
      - Product: Install a specific product (maintains collection.json integrity)
        Example: logforge templates install microsoft/windows --product
        Example: logforge templates install aws/cloudtrail --product
    
    Individual templates are enabled/disabled via generator configuration in config.yaml.
    """
    try:
        # Get API URL from config or parameter
        if api_url is None:
            config = load_config()
            api_url = config.templates.community_api_url
        
        client = CommunityAPIClient(base_url=api_url)
        
        # Handle --list-vendors option
        if list_vendors:
            console.print("[cyan]Available Vendors:[/cyan]\n")
            
            try:
                # Use search_templates to get full hierarchy with product counts
                result = client.search_templates(page=1, page_size=100)
                vendors = result.get('vendors', [])
                
                if not vendors:
                    console.print("[yellow]No vendors found in registry[/yellow]")
                    return
                
                for vendor_data in vendors:
                    vendor_id = vendor_data.get('id', 'unknown')
                    vendor_name = vendor_data.get('vendor', vendor_id)
                    products = vendor_data.get('products', [])
                    product_count = len(products)
                    
                    console.print(f"[bold cyan]{vendor_name}[/bold cyan] ([dim]{vendor_id}[/dim])")
                    console.print(f"  [green]{product_count} product(s)[/green]")
                    console.print(f"  [dim]Install: logforge templates install {vendor_id} --vendor[/dim]\n")
                
                return
            except CommunityAPIError as e:
                console.print(f"[red]Error listing vendors: {e}[/red]")
                raise typer.Exit(code=1)
        
        # Require vendor_or_product if not listing
        if not vendor_or_product:
            console.print("[red]Error: Must specify vendor or product ID, or use --list-vendors[/red]")
            console.print("[dim]Hint: Use 'logforge templates install --list-vendors' to see available vendors[/dim]")
            console.print("[dim]Examples:[/dim]")
            console.print("[dim]  Vendor:  logforge templates install microsoft --vendor[/dim]")
            console.print("[dim]  Product: logforge templates install microsoft/windows --product[/dim]")
            raise typer.Exit(code=1)
        
        # Load config for paths
        config = load_config()
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / 'default'
        default_path.mkdir(parents=True, exist_ok=True)
        
        if local_file:
            # Install from local .forge file
            if not local_file.exists():
                console.print(f"[red]Error: File not found: {local_file}[/red]")
                raise typer.Exit(code=1)
            
            console.print(f"[cyan]Installing from local package: {local_file}[/cyan]")
            
            from logforge.community.package import extract_forge_package, validate_package_structure, install_package
            import tempfile
            
            with tempfile.TemporaryDirectory(prefix='logforge-') as temp_dir:
                temp_path = Path(temp_dir)
                extract_to = temp_path / 'extracted'
                vendor_dir = extract_forge_package(local_file, extract_to, validate=True)
                validate_package_structure(vendor_dir)
                
                vendor_id = vendor_dir.name
                installed_dir = install_package(
                    vendor_dir,
                    default_path,
                    vendor_id=vendor_id,
                    overwrite=overwrite,
                    backup_count=config.templates.backup_count,
                )
                
                console.print(f"[green]✓ Package installed successfully[/green]")
                console.print(f"  Location: {installed_dir}")
                return
        
        # Install from API
        # Determine if this is vendor or product installation
        parts = vendor_or_product.split('/')
        
        if vendor or len(parts) == 1:
            # Vendor-level installation
            vendor_id = parts[0].lower()
            console.print(f"[cyan]Installing vendor package: {vendor_id}[/cyan]")
            
            # Verify vendor exists
            try:
                vendor_info = client.get_vendor_detail(vendor_id)
                vendor_name = vendor_info.get('vendor', vendor_id)
                products = vendor_info.get('products', [])
                console.print(f"[dim]Vendor: {vendor_name} ({len(products)} products)[/dim]")
            except CommunityAPINotFoundError:
                console.print(f"[red]Error: Vendor '{vendor_id}' not found[/red]")
                raise typer.Exit(code=1)
            
            # Download progress callback
            def progress_callback(bytes_downloaded: int, total_bytes: int):
                if total_bytes > 0:
                    percent = (bytes_downloaded / total_bytes) * 100
                    console.print(f"\r[dim]Downloading: {bytes_downloaded:,} / {total_bytes:,} bytes ({percent:.1f}%)[/dim]", end="")
            
            # Download and install
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Downloading...", total=None)
                
                installed_dir = download_and_install_vendor(
                    client=client,
                    vendor_id=vendor_id,
                    target_dir=default_path,
                    overwrite=overwrite,
                    progress_callback=lambda b, t: progress.update(task, completed=b, total=t),
                    backup_count=config.templates.backup_count,
                )
                
                progress.update(task, completed=True, description="[green]Complete")
            
            console.print(f"\n[green]✓ Vendor package installed successfully[/green]")
            console.print(f"  Location: {installed_dir}")
            console.print(f"[dim]Configure generators in config.yaml to enable/disable individual templates[/dim]")
        
        elif product or len(parts) == 2:
            # Product-level installation
            vendor_id = parts[0].lower()
            product_id = parts[1].lower()
            console.print(f"[cyan]Installing product: {vendor_id}/{product_id}[/cyan]")
            
            # Verify product exists
            try:
                product_info = client.get_product_detail(vendor_id, product_id)
                product_name = product_info.get('product', product_id)
                collection_version = product_info.get('collection_version', 'N/A')
                data_sources = product_info.get('data_sources', [])
                total_templates = sum(len(ds.get('event_types', [])) for ds in data_sources)
                console.print(f"[dim]Product: {product_name} (v{collection_version}, {total_templates} templates)[/dim]")
            except CommunityAPINotFoundError:
                console.print(f"[red]Error: Product '{vendor_id}/{product_id}' not found[/red]")
                console.print(f"[dim]Use 'logforge templates browse --vendor {vendor_id}' to see available products[/dim]")
                raise typer.Exit(code=1)
            
            # Download progress callback
            def progress_callback(bytes_downloaded: int, total_bytes: int):
                if total_bytes > 0:
                    percent = (bytes_downloaded / total_bytes) * 100
                    console.print(f"\r[dim]Downloading: {bytes_downloaded:,} / {total_bytes:,} bytes ({percent:.1f}%)[/dim]", end="")
            
            # Download and install product
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Downloading...", total=None)
                
                installed_dir = download_and_install_product(
                    client=client,
                    vendor_id=vendor_id,
                    product_id=product_id,
                    target_dir=default_path,
                    overwrite=overwrite,
                    progress_callback=lambda b, t: progress.update(task, completed=b, total=t),
                )
                
                progress.update(task, completed=True, description="[green]Complete")
            
            console.print(f"\n[green]✓ Product installed successfully[/green]")
            console.print(f"  Location: {installed_dir}")
            console.print(f"[dim]Configure generators in config.yaml to enable/disable individual templates[/dim]")
        
        else:
            # Invalid - too many parts (individual template not supported)
            console.print(f"[red]Error: Individual template installation not supported[/red]")
            console.print(f"[yellow]Install at product or vendor level:[/yellow]")
            if len(parts) >= 2:
                vendor_id = parts[0]
                product_id = parts[1]
                console.print(f"[cyan]  Product: logforge templates install {vendor_id}/{product_id} --product[/cyan]")
                console.print(f"[cyan]  Vendor:  logforge templates install {vendor_id} --vendor[/cyan]")
            else:
                console.print(f"[cyan]  Vendor:  logforge templates install {parts[0]} --vendor[/cyan]")
            console.print(f"[dim]Individual templates are enabled/disabled via generator configuration[/dim]")
            raise typer.Exit(code=1)
    
    except CommunityAPINotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except CommunityAPIRateLimitError as e:
        console.print(f"[red]Rate limit exceeded: {e}[/red]")
        raise typer.Exit(code=1)
    except PackageError as e:
        console.print(f"[red]Package error: {e}[/red]")
        raise typer.Exit(code=1)
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", exc_info=True)
        raise typer.Exit(code=1)


@app.command("update")
def templates_update(
    vendor_id: Optional[str] = typer.Argument(None, help="Vendor ID to update (all vendors if omitted)"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check for updates without installing"),
) -> None:
    """Update templates from community registry."""
    try:
        config = load_config()
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / 'default'
        
        # Get API URL from config or parameter
        if api_url is None:
            api_url = config.templates.community_api_url
        
        client = CommunityAPIClient(base_url=api_url)
        
        # Get list of vendors to check
        if vendor_id:
            vendors_to_check = [vendor_id.lower()]
        else:
            # Find all installed vendors
            if not default_path.exists():
                console.print("[yellow]No templates installed[/yellow]")
                return
            
            vendors_to_check = [
                d.name for d in default_path.iterdir()
                if d.is_dir() and not d.name.startswith('.')
            ]
        
        if not vendors_to_check:
            console.print("[yellow]No vendors to update[/yellow]")
            return
        
        console.print(f"[cyan]Checking for updates...[/cyan]\n")
        
        updates_available = []
        
        for vendor_id in vendors_to_check:
            # Check if vendor exists locally
            vendor_dir = default_path / vendor_id
            if not vendor_dir.exists():
                console.print(f"[dim]Skipping {vendor_id}: not installed locally[/dim]")
                continue
            
            try:
                # Get vendor info from API
                vendor_info = client.get_vendor_detail(vendor_id)
                
                # Check each product for updates
                products = vendor_info.get('products', [])
                for product_id in products:
                    try:
                        product_info = client.get_product_detail(vendor_id, product_id)
                        remote_version = product_info.get('collection_version')
                        
                        # Get local version
                        local_version = get_local_collection_version(
                            vendor_id,
                            product_id,
                            templates_path
                        )
                        
                        if remote_version and compare_versions(local_version, remote_version) < 0:
                            updates_available.append({
                                'vendor_id': vendor_id,
                                'product_id': product_id,
                                'local_version': local_version,
                                'remote_version': remote_version,
                            })
                            
                            status = format_version_status(local_version, remote_version)
                            console.print(f"[yellow]{vendor_id}/{product_id}:[/yellow] {status}")
                        elif remote_version:
                            status = format_version_status(local_version, remote_version)
                            console.print(f"[dim]{vendor_id}/{product_id}:[/dim] {status}")
                    
                    except CommunityAPINotFoundError:
                        console.print(f"[dim]Skipping {vendor_id}/{product_id}: not found in registry[/dim]")
                        continue
                    except Exception as e:
                        console.print(f"[yellow]Warning: Failed to check {vendor_id}/{product_id}: {e}[/yellow]")
                        continue
            
            except CommunityAPINotFoundError:
                console.print(f"[dim]Skipping {vendor_id}: not found in registry[/dim]")
                continue
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to check {vendor_id}: {e}[/yellow]")
                continue
        
        if not updates_available:
            console.print("\n[green]All templates are up to date[/green]")
            return
        
        if dry_run:
            console.print(f"\n[yellow]Dry run: {len(updates_available)} update(s) available[/yellow]")
            console.print("[dim]Run without --dry-run to install updates[/dim]")
            return
        
        # Group updates by vendor
        vendor_updates = {}
        for update in updates_available:
            vendor_id = update['vendor_id']
            if vendor_id not in vendor_updates:
                vendor_updates[vendor_id] = []
            vendor_updates[vendor_id].append(update)
        
        # Install updates
        console.print(f"\n[cyan]Installing {len(updates_available)} update(s)...[/cyan]\n")
        
        for vendor_id, updates in vendor_updates.items():
            console.print(f"[cyan]Updating {vendor_id}...[/cyan]")
            
            try:
                installed_dir = download_and_install_vendor(
                    client=client,
                    vendor_id=vendor_id,
                    target_dir=default_path,
                    overwrite=True,  # Always overwrite for updates
                    backup_count=config.templates.backup_count,
                )
                
                console.print(f"[green]✓ Updated {vendor_id}[/green]")
                
                for update in updates:
                    console.print(f"  {update['product_id']}: {update['local_version']} → {update['remote_version']}")
            
            except Exception as e:
                console.print(f"[red]Failed to update {vendor_id}: {e}[/red]")
                continue
        
        console.print("\n[green]Update complete[/green]")
    
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", exc_info=True)
        raise typer.Exit(code=1)


@app.command("compare")
def templates_compare(
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        envvar="LOGFORGE_COMMUNITY_API_URL",
        help="Community API URL"
    ),
) -> None:
    """Compare local templates with remote registry (show installed, available, updates)."""
    try:
        config = load_config()
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / 'default'
        
        # Get API URL from config or parameter
        if api_url is None:
            api_url = config.templates.community_api_url
        
        client = CommunityAPIClient(base_url=api_url)
        
        # Get local templates
        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()
        local_template_ids = set(local_templates.keys())
        
        # Get remote vendors
        try:
            remote_vendors = client.get_vendors()
        except CommunityAPIError as e:
            console.print(f"[red]Error fetching remote templates: {e}[/red]")
            raise typer.Exit(code=1)
        
        # Build remote template set
        remote_template_ids = set()
        remote_vendor_products = {}
        
        for vendor_data in remote_vendors:
            vendor_id = vendor_data.get('id')
            products = vendor_data.get('products', [])
            
            for product_id in products:
                try:
                    product_info = client.get_product_detail(vendor_id, product_id)
                    data_sources = product_info.get('data_sources', [])
                    
                    for ds_data in data_sources:
                        templates = ds_data.get('event_types', [])
                        for template in templates:
                            template_id = template.get('id')
                            if template_id:
                                remote_template_ids.add(template_id)
                    
                    if vendor_id not in remote_vendor_products:
                        remote_vendor_products[vendor_id] = set()
                    remote_vendor_products[vendor_id].add(product_id)
                except Exception:
                    continue
        
        # Compare
        only_local = local_template_ids - remote_template_ids
        only_remote = remote_template_ids - local_template_ids
        both = local_template_ids & remote_template_ids
        
        console.print(f"\n[bold]Template Comparison[/bold]\n")
        console.print(f"  [green]Installed locally:[/green] {len(local_template_ids)} templates")
        console.print(f"  [cyan]Available remotely:[/cyan] {len(remote_template_ids)} templates")
        console.print(f"  [yellow]Installed & up to date:[/yellow] {len(both)} templates")
        
        if only_local:
            console.print(f"\n[dim]Templates installed locally but not in registry ({len(only_local)}):[/dim]")
            for tid in sorted(list(only_local))[:10]:
                console.print(f"  • {tid}")
            if len(only_local) > 10:
                console.print(f"  ... and {len(only_local) - 10} more")
        
        if only_remote:
            console.print(f"\n[dim]Templates available remotely but not installed ({len(only_remote)}):[/dim]")
            console.print(f"  [dim]Use 'logforge templates search' or 'logforge templates browse' to discover them[/dim]")
        
        # Check for vendors installed locally
        if default_path.exists():
            local_vendors = {d.name for d in default_path.iterdir() if d.is_dir() and not d.name.startswith('.')}
            console.print(f"\n[bold]Installed Vendors:[/bold] {', '.join(sorted(local_vendors))}")
        
        console.print(f"\n[bold]Available Vendors in Registry:[/bold] {', '.join(sorted(remote_vendor_products.keys()))}")
        console.print(f"\n[dim]Use 'logforge templates update' to check for updates[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", exc_info=True)
        raise typer.Exit(code=1)


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
