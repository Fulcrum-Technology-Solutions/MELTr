"""Template management CLI commands."""

import difflib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from meltr.cli.menu import paginate_choose
from meltr.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
    CommunityAPIRateLimitError,
)
from meltr.community.package import (
    PackageError,
    download_and_install_product,
    download_and_install_vendor,
    get_local_collection_version,
)
from meltr.community.updates import find_stale_updates
from meltr.community.version import compare_versions, format_version_status
from meltr.core.config import load_config
from meltr.core.paths import get_logforge_home
from meltr.templates.loader import TemplateLoader
from meltr.templates.metadata import TemplateMetadata
from meltr.templates.validator import validate_template

app = typer.Typer(name="templates", help="Template management", invoke_without_command=True)
console = Console()
_log = logging.getLogger(__name__)


def _backup_custom_template_files(home: Path, template_id: str, j2: Path, meta: Path) -> Path:
    """Copy existing custom .j2 / .meta.yaml into backups/templates/. Returns backup directory."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = template_id.replace("/", "__")
    backup_dir = home / "backups" / "templates" / stamp / safe
    backup_dir.mkdir(parents=True, exist_ok=True)
    if j2.is_file():
        shutil.copy2(j2, backup_dir / j2.name)
    if meta.is_file():
        shutil.copy2(meta, backup_dir / meta.name)
    return backup_dir


def _print_unified_diff_file(a: Path, b: Path, from_name: str, to_name: str) -> bool:
    """Print unified diff from ``a`` (reference) to ``b``. Returns True if there are differences."""
    a_lines = a.read_text(encoding="utf-8").splitlines(keepends=True)
    b_lines = b.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(a_lines, b_lines, fromfile=from_name, tofile=to_name, lineterm="")
    )
    if not diff:
        return False
    for line in diff:
        console.print(line)
    return True


@app.callback(invoke_without_command=True)
def templates_callback(ctx: typer.Context) -> None:
    """Template management - interactive menu or use subcommands."""
    if ctx.invoked_subcommand is None:
        _templates_interactive_menu()


def _templates_interactive_menu() -> None:
    """Interactive templates menu."""
    while True:
        console.print("\n[bold]Template Management[/bold]\n")

        menu = Panel(
            "[cyan]1.[/cyan] Browse templates (hierarchical)\n"
            "[cyan]2.[/cyan] Search templates\n"
            "[cyan]3.[/cyan] List local templates\n"
            "[cyan]4.[/cyan] Compare local vs remote\n"
            "[cyan]5.[/cyan] Install templates\n"
            "[cyan]6.[/cyan] View template info\n"
            "[cyan]7.[/cyan] Exit",
            title="Main Menu",
            border_style="blue",
        )
        console.print(menu)

        choice = Prompt.ask(
            "\nSelect option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1"
        )

        if choice == "1":
            _browse_templates_interactive()
        elif choice == "2":
            _search_templates_interactive()
        elif choice == "3":
            _list_local_templates_interactive()
        elif choice == "4":
            templates_compare()
        elif choice == "5":
            _install_templates_interactive()
        elif choice == "6":
            _view_template_info_interactive()
        elif choice == "7":
            break


def _paginate_templates(
    items: list[tuple[str, Any]],
    page_size: int = 20,
    title: str = "",
    show_index: bool = True,
) -> int | None:
    """Display paginated template list and get user selection."""
    return paginate_choose(
        items,
        console=console,
        page_size=page_size,
        title=title,
        show_index=show_index,
    )


def _count_data_source_templates(data_sources: list[dict]) -> int:
    """Count templates across data source payload variants."""
    total = 0
    for data_source in data_sources:
        total += len(data_source.get("templates", []))
        total += len(data_source.get("event_types", []))
    return total


def _get_installed_vendors(config) -> set[str]:
    """Get set of installed vendor IDs.

    Args:
        config: Configuration object

    Returns:
        Set of vendor ID strings
    """
    templates_path = Path(config.templates.local_path)
    default_path = templates_path / "default"

    if not default_path.exists():
        return set()

    vendors = set()
    for vendor_dir in default_path.iterdir():
        if vendor_dir.is_dir() and not vendor_dir.name.startswith("."):
            vendors.add(vendor_dir.name)

    return vendors


def _get_installed_products(config, vendor_id: str) -> set[str]:
    """Get set of installed product IDs for a vendor.

    Args:
        config: Configuration object
        vendor_id: Vendor identifier

    Returns:
        Set of product ID strings
    """
    templates_path = Path(config.templates.local_path)
    default_path = templates_path / "default"
    vendor_dir = default_path / vendor_id

    if not vendor_dir.exists() or not vendor_dir.is_dir():
        return set()

    products = set()
    for product_dir in vendor_dir.iterdir():
        if product_dir.is_dir() and not product_dir.name.startswith("."):
            # Check if it's a product (has collection.json)
            collection_json = product_dir / "collection.json"
            if collection_json.exists():
                products.add(product_dir.name)

    return products


def _is_vendor_installed(config, vendor_id: str) -> bool:
    """Check if vendor is installed.

    Args:
        config: Configuration object
        vendor_id: Vendor identifier

    Returns:
        True if vendor directory exists
    """
    templates_path = Path(config.templates.local_path)
    default_path = templates_path / "default"
    vendor_dir = default_path / vendor_id
    return vendor_dir.exists() and vendor_dir.is_dir()


def _is_product_installed(config, vendor_id: str, product_id: str) -> bool:
    """Check if product is installed.

    Args:
        config: Configuration object
        vendor_id: Vendor identifier
        product_id: Product identifier

    Returns:
        True if product directory exists with collection.json
    """
    templates_path = Path(config.templates.local_path)
    default_path = templates_path / "default"
    product_dir = default_path / vendor_id / product_id

    if not product_dir.exists() or not product_dir.is_dir():
        return False

    collection_json = product_dir / "collection.json"
    return collection_json.exists()


def _browse_templates_interactive() -> None:
    """Interactive hierarchical template browsing."""
    try:
        config = load_config()
        api_url = config.templates.community_api_url
        client = CommunityAPIClient(base_url=api_url)

        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()
        local_template_ids = set(local_templates.keys())

        # Step 1: Select vendor
        result = client.search_templates(page=1, page_size=100)
        vendors = result.get("vendors", [])

        if not vendors:
            console.print("[yellow]No vendors found[/yellow]")
            return

        items = []
        for vendor_data in vendors:
            vendor_id = vendor_data.get("id", "unknown")
            vendor_name = vendor_data.get("vendor", vendor_id)
            products = vendor_data.get("products", [])
            items.append((f"{vendor_name} ({len(products)} products)", vendor_id))

        selection = _paginate_templates(items, title="Select Vendor")
        if selection is None or selection < 0:
            return

        selected_vendor_id = items[selection][1]

        # Step 2: Select product
        vendor_result = client.search_templates(vendor_id=selected_vendor_id, page=1, page_size=100)
        vendor_data = vendor_result.get("vendors", [0])[0] if vendor_result.get("vendors") else None

        if not vendor_data:
            console.print("[yellow]Vendor not found[/yellow]")
            return

        products = vendor_data.get("products", [])
        if not products:
            console.print("[yellow]No products found for this vendor[/yellow]")
            return

        items = []
        for product_data in products:
            product_id = product_data.get("product_id", "unknown")
            product_name = product_data.get("product", product_id)
            data_sources = product_data.get("data_sources", [])
            total_templates = _count_data_source_templates(data_sources)
            items.append((f"{product_name} ({total_templates} templates)", product_id))

        selection = _paginate_templates(
            items, title=f"Products: {vendor_data.get('vendor', selected_vendor_id)}"
        )
        if selection is None or selection < 0:
            return

        selected_product_id = items[selection][1]

        # Step 3: Show templates for product
        product_data = products[selection]
        data_sources = product_data.get("data_sources", [])

        all_templates = []
        for ds_data in data_sources:
            templates = ds_data.get("templates", [])
            for template in templates:
                template_id = template.get("event_type_id") or template.get("id")
                if template_id:
                    # Store full template info including vendor/product for installation
                    all_templates.append(
                        (
                            template_id,
                            template,
                            ds_data.get("data_source_id"),
                            selected_vendor_id,
                            selected_product_id,
                        )
                    )

        if not all_templates:
            console.print("[yellow]No templates found[/yellow]")
            return

        # Display templates with status
        items = []
        for template_id, template, ds_id, vendor_id, product_id in all_templates:
            template_name = template.get("name", template_id)
            is_installed = template_id in local_template_ids
            status = "[green]✓[/green]" if is_installed else "[dim]○[/dim]"
            items.append(
                (f"{status} {template_name} ({ds_id})", (template_id, vendor_id, product_id))
            )

        selection = _paginate_templates(
            items, title=f"Templates: {product_data.get('product', selected_product_id)}"
        )
        if selection is None or selection < 0:
            return

        selected_template_id, vendor_id, product_id = items[selection][1]
        console.print(f"\n[green]Selected: {selected_template_id}[/green]")

        # Offer to install if not installed
        if selected_template_id not in local_template_ids:
            if Confirm.ask("\n[yellow]Install this template?", default=False):
                product_path = f"{vendor_id}/{product_id}"
                console.print(f"[cyan]Installing product: {product_path}[/cyan]")
                try:
                    _do_install_template(product_path, product=True, api_url=api_url)
                    console.print("[green]✓ Installation completed successfully[/green]")
                except Exception as e:
                    _log.debug("Install from browse failed", exc_info=True)
                    console.print(f"[red]Installation failed: {e}[/red]")

    except Exception as e:
        _log.debug("Browse templates interactive failed", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def _search_templates_interactive() -> None:
    """Interactive template search."""
    try:
        config = load_config()
        api_url = config.templates.community_api_url
        client = CommunityAPIClient(base_url=api_url)

        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()
        local_template_ids = set(local_templates.keys())

        # Get search query
        query = Prompt.ask("\nSearch query (leave empty to browse all)", default="")
        query = query.strip() if query else None

        # Optional filters
        vendor = Prompt.ask("Filter by vendor (optional)", default="")
        vendor = vendor.strip() if vendor else None

        product = Prompt.ask("Filter by product (optional)", default="")
        product = product.strip() if product else None

        # Search
        result = client.search_templates(
            query=query,
            vendor_id=vendor,
            product_id=product,
            page=1,
            page_size=100,
        )

        vendors = result.get("vendors", [])
        if not vendors:
            console.print("[yellow]No templates found[/yellow]")
            return

        # Flatten templates for display
        all_templates = []
        for vendor_data in vendors:
            vendor_id = vendor_data.get("id", "unknown")
            for product_data in vendor_data.get("products", []):
                product_id = product_data.get("product_id", "unknown")
                for ds_data in product_data.get("data_sources", []):
                    templates = ds_data.get("templates", [])
                    for template in templates:
                        template_id = template.get("event_type_id") or template.get("id")
                        if template_id:
                            all_templates.append((template_id, template, vendor_id, product_id))

        if not all_templates:
            console.print("[yellow]No templates found[/yellow]")
            return

        # Display with pagination
        items = []
        for template_id, template, vendor_id, product_id in all_templates:
            template_name = template.get("name", template_id)
            is_installed = template_id in local_template_ids
            status = "[green]✓[/green]" if is_installed else "[dim]○[/dim]"
            # Store vendor/product with template_id for installation
            items.append(
                (
                    f"{status} {template_name} ({vendor_id}/{product_id})",
                    (template_id, vendor_id, product_id),
                )
            )

        selection = _paginate_templates(items, title=f"Search Results ({len(items)} templates)")
        if selection is None or selection < 0:
            return

        selected_template_id, vendor_id, product_id = items[selection][1]
        console.print(f"\n[green]Selected: {selected_template_id}[/green]")

        # Offer to install if not installed
        if selected_template_id not in local_template_ids:
            if Confirm.ask("\n[yellow]Install this template?", default=False):
                product_path = f"{vendor_id}/{product_id}"
                console.print(f"[cyan]Installing product: {product_path}[/cyan]")
                try:
                    _do_install_template(product_path, product=True, api_url=api_url)
                    console.print("[green]✓ Installation completed successfully[/green]")
                except Exception as e:
                    _log.debug("Install from search failed", exc_info=True)
                    console.print(f"[red]Installation failed: {e}[/red]")

    except Exception as e:
        _log.debug("Search templates interactive failed", exc_info=True)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def _list_local_templates_interactive() -> None:
    """Interactive local templates list with pagination."""
    try:
        config = load_config()
        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()

        if not local_templates:
            console.print("[yellow]No local templates found[/yellow]")
            return

        # Build display items
        items = []
        for template_id, template_info in sorted(local_templates.items()):
            location = template_info.location
            location_mark = "[yellow]⚠[/yellow]" if location == "custom" else "[green]✓[/green]"
            items.append((f"{location_mark} {template_id} ({location})", template_id))

        selection = _paginate_templates(items, title=f"Local Templates ({len(items)} total)")
        if selection is None or selection < 0:
            return

        selected_template_id = items[selection][1]
        templates_info(selected_template_id)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def _install_templates_interactive() -> None:
    """Interactive template installation."""
    console.print("\n[bold]Install Templates[/bold]\n")
    console.print("[cyan]Options:[/cyan]")
    console.print("  [1] Browse and install")
    console.print("  [2] Search and install")
    console.print("  [3] Install by vendor/product")

    choice = Prompt.ask("\nSelect option", choices=["1", "2", "3"], default="1")

    if choice == "1":
        _browse_templates_interactive()
    elif choice == "2":
        _search_templates_interactive()
    elif choice == "3":
        try:
            config = load_config()
            api_url = config.templates.community_api_url
            client = CommunityAPIClient(base_url=api_url)

            # Step 1: Select vendor
            result = client.search_templates(page=1, page_size=100)
            vendors = result.get("vendors", [])

            if not vendors:
                console.print("[yellow]No vendors found[/yellow]")
                return

            items = []
            installed_vendors = _get_installed_vendors(config)
            for vendor_data in vendors:
                vendor_id = vendor_data.get("id", "unknown")
                vendor_name = vendor_data.get("vendor", vendor_id)
                products = vendor_data.get("products", [])
                is_installed = vendor_id in installed_vendors
                status = "[green]✓[/green]" if is_installed else "[dim]○[/dim]"
                installed_text = " [installed]" if is_installed else ""
                items.append(
                    (
                        f"{status} {vendor_name} ({len(products)} products){installed_text}",
                        vendor_id,
                    )
                )

            selection = _paginate_templates(items, title="Select Vendor")
            if selection is None or selection < 0:
                return

            selected_vendor_id = items[selection][1]

            # Step 2: Choose install level
            vendor_result = client.search_templates(
                vendor_id=selected_vendor_id, page=1, page_size=100
            )
            vendor_data = (
                vendor_result.get("vendors", [0])[0] if vendor_result.get("vendors") else None
            )

            if not vendor_data:
                console.print("[yellow]Vendor not found[/yellow]")
                return

            products = vendor_data.get("products", [])
            if not products:
                console.print("[yellow]No products found for this vendor[/yellow]")
                return

            console.print(
                f"\n[bold]Install Options for {vendor_data.get('vendor', selected_vendor_id)}[/bold]\n"
            )
            console.print("  [1] Install all products from vendor")
            console.print("  [2] Select specific product")
            console.print("  [3] Cancel")

            install_choice = Prompt.ask("\nSelect option", choices=["1", "2", "3"], default="3")

            if install_choice == "1":
                # Install all products from vendor
                is_vendor_installed = _is_vendor_installed(config, selected_vendor_id)
                if is_vendor_installed:
                    if Confirm.ask(
                        f"\n[yellow]Upgrade all products from {vendor_data.get('vendor', selected_vendor_id)}?[/yellow]",
                        default=False,
                    ):
                        _do_install_template(selected_vendor_id, vendor=True, overwrite=True)
                else:
                    if Confirm.ask(
                        f"\n[yellow]Install all products from {vendor_data.get('vendor', selected_vendor_id)}?[/yellow]",
                        default=False,
                    ):
                        _do_install_template(selected_vendor_id, vendor=True)
            elif install_choice == "2":
                # Select specific product
                items = []
                installed_products = _get_installed_products(config, selected_vendor_id)
                templates_path = Path(config.templates.local_path)

                for product_data in products:
                    product_id = product_data.get("product_id", "unknown")
                    product_name = product_data.get("product", product_id)
                    data_sources = product_data.get("data_sources", [])
                    total_templates = _count_data_source_templates(data_sources)
                    is_installed = product_id in installed_products
                    status = "[green]✓[/green]" if is_installed else "[dim]○[/dim]"
                    installed_text = " [installed]" if is_installed else ""
                    items.append(
                        (
                            f"{status} {product_name} ({total_templates} templates){installed_text}",
                            product_id,
                        )
                    )

                selection = _paginate_templates(items, title="Select Product")
                if selection is None or selection < 0:
                    return

                selected_product_id = items[selection][1]
                product_path = f"{selected_vendor_id}/{selected_product_id}"

                # Check if product is installed and get version info
                is_product_installed = _is_product_installed(
                    config, selected_vendor_id, selected_product_id
                )

                if is_product_installed:
                    # Get version info for upgrade
                    try:
                        local_version = get_local_collection_version(
                            selected_vendor_id, selected_product_id, templates_path
                        )
                        product_info = client.get_product_detail(
                            selected_vendor_id, selected_product_id
                        )
                        remote_version = product_info.get("collection_version", "N/A")

                        if (
                            local_version
                            and remote_version
                            and compare_versions(local_version, remote_version) < 0
                        ):
                            # Update available
                            status_text = format_version_status(local_version, remote_version)
                            if Confirm.ask(
                                f"\n[yellow]Upgrade {product_path}? {status_text}[/yellow]",
                                default=False,
                            ):
                                _do_install_template(product_path, product=True, overwrite=True)
                        else:
                            # Already up to date or can't compare
                            if local_version:
                                if Confirm.ask(
                                    f"\n[yellow]Reinstall {product_path} (v{local_version})?[/yellow]",
                                    default=False,
                                ):
                                    _do_install_template(product_path, product=True, overwrite=True)
                            else:
                                if Confirm.ask(
                                    f"\n[yellow]Reinstall {product_path}?[/yellow]", default=False
                                ):
                                    _do_install_template(product_path, product=True, overwrite=True)
                    except Exception:
                        # If version check fails, just offer reinstall
                        if Confirm.ask(
                            f"\n[yellow]Reinstall {product_path}?[/yellow]", default=False
                        ):
                            _do_install_template(product_path, product=True, overwrite=True)
                else:
                    if Confirm.ask(f"\n[yellow]Install {product_path}?[/yellow]", default=False):
                        _do_install_template(product_path, product=True)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)


def _view_template_info_interactive() -> None:
    """Interactive template info viewer."""
    template_id = Prompt.ask("\nTemplate ID")
    if template_id:
        templates_info(template_id)


@app.command("list")
def templates_list(
    local_only: bool = typer.Option(False, "--local", help="Show only local templates"),
    remote_only: bool = typer.Option(False, "--remote", help="Show only remote templates"),
    custom_only: bool = typer.Option(False, "--custom-only", help="Show only custom templates"),
    show_remote: bool = typer.Option(
        False, "--show-remote", help="Include remote templates with installed status"
    ),
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
    ),
    page: int = typer.Option(1, "--page", help="Page number (for paginated output)"),
    page_size: int = typer.Option(20, "--page-size", help="Results per page"),
) -> None:
    """List available templates (local and/or remote)."""
    from meltr.core.config import load_config

    try:
        config = load_config()

        # Get local templates
        loader = TemplateLoader(config)
        local_templates = loader.discover_templates()
        local_template_ids = set(local_templates.keys())

        # Filter local templates
        if custom_only:
            templates_to_show = {
                tid: t for tid, t in local_templates.items() if t.location == "custom"
            }
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
                for vendor_data in result.get("vendors", []):
                    for product_data in vendor_data.get("products", []):
                        for ds_data in product_data.get("data_sources", []):
                            for template in ds_data.get("templates", []):
                                template_id = template.get("id")
                                if template_id:
                                    remote_templates[template_id] = {
                                        "name": template.get("name", template_id),
                                        "vendor": vendor_data.get("id"),
                                        "product": product_data.get("product_id"),
                                        "format": template.get("format", "N/A"),
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
                "format": template_info.metadata.format,
                "vendor": template_info.vendor,
                "product": template_info.product,
                "location": template_info.location,
            }

        # Add remote templates based on options
        if remote_only:
            unified_templates = {}
            for tid, remote_info in remote_templates.items():
                unified_templates[tid] = {
                    "format": remote_info["format"],
                    "vendor": remote_info["vendor"],
                    "product": remote_info["product"],
                    "location": "remote",
                }
        elif show_remote:
            # Merge remote templates (only add if not already in local)
            for tid, remote_info in remote_templates.items():
                if tid not in unified_templates:
                    unified_templates[tid] = {
                        "format": remote_info["format"],
                        "vendor": remote_info["vendor"],
                        "product": remote_info["product"],
                        "location": "remote",
                    }

        # Sort templates
        sorted_template_ids = sorted(unified_templates.keys())
        total_templates = len(sorted_template_ids)

        # Pagination
        total_pages = (total_templates + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_templates)
        page_template_ids = sorted_template_ids[start_idx:end_idx]

        # Display as table
        table = Table(title=f"Templates (Page {page} of {total_pages})")
        table.add_column("ID", style="cyan")
        table.add_column("Installed", style="green")
        table.add_column("Location", style="dim")
        table.add_column("Format", style="yellow")
        table.add_column("Vendor", style="magenta")
        table.add_column("Product", style="blue")

        for template_id in page_template_ids:
            template_info = unified_templates[template_id]

            # Determine installed status
            is_installed = template_id in local_template_ids
            installed_mark = "[green]✓[/green]" if is_installed else "[dim]-[/dim]"

            table.add_row(
                template_id,
                installed_mark,
                template_info["location"],
                template_info["format"],
                template_info["vendor"],
                template_info["product"],
            )

        console.print(table)

        local_count = len([t for t in unified_templates.keys() if t in local_template_ids])
        remote_count = len([t for t in unified_templates.keys() if t not in local_template_ids])

        summary = f"\n[dim]Showing {len(page_template_ids)} of {total_templates} templates"
        if show_remote or remote_only:
            summary += f" ({local_count} installed, {remote_count} available remotely)"
        summary += "[/dim]"
        console.print(summary)

        if total_pages > 1:
            console.print(f"[dim]Use --page to navigate (1-{total_pages})[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("preview")
def templates_preview(
    template_id: str = typer.Argument(..., help="Template ID to preview"),
    count: int = typer.Option(1, "--count", min=1, max=20, help="Number of sample events"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON response"),
) -> None:
    """Render sample events from a template via the management API."""
    from meltr.cli.api_client import get_api_client

    try:
        client = get_api_client(api_url=api_url, api_key=api_key)
        client.require_service_running()
        response = client.post(
            f"/api/templates/{template_id}/preview",
            json={"count": count},
        )
        if response.status_code == 404:
            console.print(f"[red]Error: Template '{template_id}' not found[/red]")
            raise typer.Exit(code=1)
        if response.status_code == 422:
            detail = response.json().get("detail", response.text)
            console.print(f"[red]Preview failed: {detail}[/red]")
            raise typer.Exit(code=1)
        if response.status_code == 401:
            console.print("[red]Error: Invalid or missing API key[/red]")
            raise typer.Exit(code=1)
        if response.status_code != 200:
            console.print(f"[red]API error: HTTP {response.status_code}[/red]")
            raise typer.Exit(code=1)

        data = response.json()
        if json_output:
            console.print(json.dumps(data, indent=2))
            return

        console.print(
            f"\n[bold]Preview: {template_id}[/bold] ({data.get('count', count)} event(s))\n"
        )
        for index, event in enumerate(data.get("events", []), start=1):
            console.print(f"[dim]--- Event {index} ---[/dim]")
            console.print(event)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("check-updates")
def templates_check_updates(
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        envvar="MELTR_COMMUNITY_API_URL",
        help="Community API URL",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON response"),
) -> None:
    """Check installed community packages for available updates (detection only).

    Exit code is 0 when the check completes successfully, even if updates are available.
    Exit code is 1 only when the community registry cannot be reached.
    """
    try:
        config = load_config()
        if api_url is None:
            api_url = config.templates.community_api_url

        client = CommunityAPIClient(base_url=api_url)
        updates = find_stale_updates(client, Path(config.templates.local_path))

        if json_output:
            console.print(json.dumps({"updates": updates}, indent=2))
            return

        if not updates:
            console.print("[green]All installed packages are up to date[/green]")
            return

        console.print(f"[yellow]{len(updates)} update(s) available[/yellow]\n")
        for row in updates:
            status = format_version_status(row["local_version"], row["remote_version"])
            console.print(f"  [cyan]{row['vendor_id']}/{row['product_id']}:[/cyan] {status}")
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("info")
def templates_info(
    template_id: str = typer.Argument(..., help="Template ID"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Show detailed template information."""
    from meltr.core.config import load_config

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
            console.print("  [cyan]Generator:[/cyan] Yes")
            if metadata.base_frequency:
                console.print(
                    f"  [cyan]Base Frequency:[/cyan] {metadata.base_frequency} events/hour"
                )

        if metadata.documentation:
            doc = metadata.documentation
            if "display" in doc:
                display = doc["display"]
                if "title" in display:
                    console.print(f"\n  [bold]Title:[/bold] {display['title']}")
                if "tags" in display:
                    console.print(f"  [cyan]Tags:[/cyan] {', '.join(display['tags'])}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("validate")
def templates_validate(
    template_path: Path | None = typer.Option(
        None, "--path", "--file", help="Path to template file or directory"
    ),
) -> None:
    """Validate a template."""
    from meltr.core.paths import get_logforge_home

    if template_path is None:
        console.print("[red]Error: --path or --file required[/red]")
        console.print("[dim]Example: meltr templates validate --file /path/to/template.j2[/dim]")
        console.print(
            "[dim]Example: meltr templates validate --path /path/to/template/directory[/dim]"
        )
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
                resolved_path = (
                    template_path.resolve()
                    if template_path.is_absolute()
                    else Path.cwd() / template_path
                )

    # Find template.j2 and metadata.yaml
    template_j2 = None
    metadata_yaml = None

    if resolved_path.is_file():
        if resolved_path.suffix == ".j2":
            template_j2 = resolved_path
            metadata_yaml = resolved_path.parent / f"{resolved_path.stem}.meta.yaml"
        elif resolved_path.name.endswith(".meta.yaml"):
            metadata_yaml = resolved_path
            template_j2 = resolved_path.parent / f"{resolved_path.stem.replace('.meta', '')}.j2"
        else:
            console.print(
                "[red]Error: File must be a .j2 template or .meta.yaml metadata file[/red]"
            )
            console.print(f"[dim]Provided: {resolved_path}[/dim]")
            raise typer.Exit(code=1)
    elif resolved_path.is_dir():
        # Look for .j2 and .meta.yaml files in directory
        for file in resolved_path.glob("*.j2"):
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
    import shutil

    from meltr.core.config import load_config

    try:
        config = load_config()
        loader = TemplateLoader(config)

        # Find template in default
        template_info = loader.resolve_template(template_id)
        if not template_info:
            console.print(f"[red]Error: Template '{template_id}' not found[/red]")
            raise typer.Exit(code=1)

        if template_info.location == "custom":
            console.print(f"[yellow]Template '{template_id}' is already a custom template[/yellow]")
            return

        # Copy to custom directory
        default_dir = template_info.template_path.parent
        custom_base = loader.custom_path

        # Recreate directory structure in custom
        parts = template_id.split("/")
        custom_dir = custom_base
        for part in parts[:-1]:  # All but template name
            custom_dir = custom_dir / part
        custom_dir.mkdir(parents=True, exist_ok=True)

        # Copy files
        for file in default_dir.glob("*"):
            if file.is_file():
                shutil.copy2(file, custom_dir / file.name)

        console.print("[green]✓ Template copied to custom directory[/green]")
        console.print(f"  Location: {custom_dir}")
        console.print("  [dim]Edit files in custom/ to customize the template[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("revert")
def templates_revert(
    template_id: str = typer.Argument(..., help="Template ID to revert"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
) -> None:
    """Remove custom version, revert to using default."""
    import shutil

    from rich.prompt import Confirm

    from meltr.core.config import load_config

    try:
        config = load_config()
        loader = TemplateLoader(config)

        # Find template in custom
        template_info = loader.resolve_template(template_id)
        if not template_info or template_info.location != "custom":
            console.print(f"[yellow]Template '{template_id}' is not a custom template[/yellow]")
            return

        if not force:
            if not Confirm.ask(f"Remove custom version of '{template_id}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Remove custom directory
        custom_dir = template_info.template_path.parent
        shutil.rmtree(custom_dir)

        console.print("[green]✓ Custom template removed[/green]")
        console.print("  Template will now use default version")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("search")
def templates_search(
    query: str | None = typer.Argument(None, help="Search query (omit to browse all templates)"),
    vendor: str | None = typer.Option(None, "--vendor", help="Filter by vendor"),
    product: str | None = typer.Option(None, "--product", help="Filter by product"),
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
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

        vendors = result.get("vendors", [])
        total = result.get("total", 0)

        if not vendors:
            console.print("[yellow]No templates found[/yellow]")
            return

        # Display results
        console.print(f"\n[bold]Found {total} vendor(s)[/bold]\n")

        for vendor_data in vendors:
            vendor_id = vendor_data.get("id", "unknown")
            vendor_name = vendor_data.get("vendor", vendor_id)

            console.print(f"[bold cyan]{vendor_name}[/bold cyan] ({vendor_id})")

            for product_data in vendor_data.get("products", []):
                product_id = product_data.get("product_id", "unknown")
                product_name = product_data.get("product", product_id)
                collection_version = product_data.get("collection_version", "N/A")

                console.print(f"  [green]└─[/green] {product_name} (v{collection_version})")

                for data_source_data in product_data.get("data_sources", []):
                    ds_id = data_source_data.get("data_source_id", "unknown")
                    ds_name = data_source_data.get("name", ds_id)

                    templates = data_source_data.get("templates", [])
                    if templates:
                        console.print(
                            f"      [yellow]└─[/yellow] {ds_name} ({len(templates)} templates)"
                        )

                        # Show first few templates
                        for template in templates[:3]:
                            template_id = template.get("event_type_id", "unknown")
                            template_name = template.get("name", template_id)
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
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("browse")
def templates_browse(
    vendor: str | None = typer.Option(
        None, "--vendor", help="Browse templates for specific vendor"
    ),
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
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
                vendors = result.get("vendors", [])

                if not vendors:
                    console.print(
                        f"[yellow]Vendor '{vendor}' not found or has no templates[/yellow]"
                    )
                    return

                vendor_data = vendors[0]  # Should only be one vendor
                vendor_id = vendor_data.get("id", vendor)
                vendor_name = vendor_data.get("vendor", vendor)

                console.print(f"[bold cyan]{vendor_name}[/bold cyan] ({vendor_id})\n")

                products = vendor_data.get("products", [])
                if not products:
                    console.print("[yellow]No products found for this vendor[/yellow]")
                    return

                for product_data in products:
                    product_id = product_data.get("product_id", "unknown")
                    product_name = product_data.get("product", product_id)
                    collection_version = product_data.get("collection_version", "N/A")

                    console.print(f"  [green]└─[/green] {product_name} (v{collection_version})")

                    data_sources = product_data.get("data_sources", [])
                    for ds_data in data_sources:
                        ds_id = ds_data.get("data_source_id", "unknown")
                        ds_name = ds_data.get("name", ds_id)
                        templates = ds_data.get("templates", [])

                        if templates:
                            console.print(
                                f"      [yellow]└─[/yellow] {ds_name} ({len(templates)} templates)"
                            )
                            for template in templates[:5]:
                                template_name = template.get(
                                    "name", template.get("event_type_id", "unknown")
                                )
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
                vendors = result.get("vendors", [])

                if not vendors:
                    console.print("[yellow]No vendors found[/yellow]")
                    return

                console.print(f"[bold]Available Vendors ({len(vendors)}):[/bold]\n")

                for vendor_data in vendors:
                    vendor_id = vendor_data.get("id", "unknown")
                    vendor_name = vendor_data.get("vendor", vendor_id)
                    vendor_desc = vendor_data.get("description", "")
                    products = vendor_data.get("products", [])
                    products_count = len(products)

                    console.print(f"[cyan]{vendor_name}[/cyan] ([dim]{vendor_id}[/dim])")
                    if vendor_desc:
                        console.print(
                            f"  [dim]{vendor_desc[:80]}{'...' if len(vendor_desc) > 80 else ''}[/dim]"
                        )
                    console.print(f"  [green]{products_count} product(s) available[/green]")
                    console.print(
                        f"  [dim]Use: meltr templates browse --vendor {vendor_id}[/dim]\n"
                    )
            except Exception:
                console.print("[yellow]Warning: Using fallback vendor list[/yellow]")
                # Fallback to basic vendor list if search fails
                vendors = client.get_vendors()
                for vendor_data in vendors:
                    vendor_id = vendor_data.get("id", "unknown")
                    vendor_name = vendor_data.get("vendor", vendor_id)
                    console.print(f"[cyan]{vendor_name}[/cyan] ([dim]{vendor_id}[/dim])")
                    console.print(
                        f"  [dim]Use: meltr templates browse --vendor {vendor_id}[/dim]\n"
                    )

    except CommunityAPIRateLimitError as e:
        console.print(f"[red]Rate limit exceeded: {e}[/red]")
        raise typer.Exit(code=1)
    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


def _do_install_template(
    vendor_or_product: str,
    vendor: bool = False,
    product: bool = False,
    api_url: str | None = None,
    overwrite: bool = False,
    local_file: Path | None = None,
) -> None:
    """Core template installation logic (called by both CLI and interactive menu).

    Args:
        vendor_or_product: Vendor ID or Product ID (vendor/product format)
        vendor: If True, install all products from vendor
        product: If True, install specific product
        api_url: Community API URL (None = use config)
        overwrite: Whether to overwrite existing installation
        local_file: Path to local .forge file (if installing from file)
    """
    try:
        # Get API URL from config or parameter
        if api_url is None:
            config = load_config()
            api_url = config.templates.community_api_url
        else:
            config = load_config()

        client = CommunityAPIClient(base_url=api_url)

        # Load config for paths
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / "default"
        default_path.mkdir(parents=True, exist_ok=True)

        def emit_template_installed_events(
            *, vendor_id: str, product_id: str | None, method: str
        ) -> None:
            """
            Emit one telemetry event per installed template under vendor/product scope.
            Non-fatal: never blocks install success.
            """
            try:
                from meltr.community.package import get_local_collection_version
                from meltr.telemetry import (
                    TelemetryClient,
                    TelemetryEvent,
                    get_actor_id,
                    telemetry_enabled,
                )

                if not telemetry_enabled():
                    return

                loader = TemplateLoader(config)
                discovered = loader.discover_templates()

                actor_id = get_actor_id()
                client_telemetry = TelemetryClient(base_api_url=config.templates.community_api_url)

                version_cache: dict[tuple[str, str], str | None] = {}

                events: list[TelemetryEvent] = []
                prefix = f"{vendor_id}/"
                product_prefix = f"{vendor_id}/{product_id}/" if product_id else None

                for tid in discovered.keys():
                    if not tid.startswith(prefix):
                        continue
                    if product_prefix and not tid.startswith(product_prefix):
                        continue
                    parts = tid.split("/")
                    if len(parts) < 4:
                        continue
                    v, prod, ds, _name = parts[0], parts[1], parts[2], parts[3]
                    key = (v, prod)
                    if key not in version_cache:
                        version_cache[key] = get_local_collection_version(v, prod, templates_path)  # type: ignore[arg-type]
                    events.append(
                        TelemetryEvent(
                            event_type="template_installed",
                            vendor_id=v,
                            product_id=prod,
                            data_source_id=ds,
                            template_id=tid,
                            collection_version=version_cache[key],
                            properties={"method": method},
                        )
                    )

                # Chunk to match server batch limits
                chunk_size = 200
                for i in range(0, len(events), chunk_size):
                    client_telemetry.post_events(
                        actor_id=actor_id, events=events[i : i + chunk_size]
                    )
            except Exception:
                _log.debug("Telemetry emit failed", exc_info=True)

        if local_file:
            # Install from local .forge file
            if not local_file.exists():
                console.print(f"[red]Error: File not found: {local_file}[/red]")
                raise typer.Exit(code=1)

            console.print(f"[cyan]Installing from local package: {local_file}[/cyan]")

            import tempfile

            from meltr.community.package import (
                extract_forge_package,
                install_package,
                validate_package_structure,
            )

            with tempfile.TemporaryDirectory(prefix="meltr-") as temp_dir:
                temp_path = Path(temp_dir)
                extract_to = temp_path / "extracted"
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

                console.print("[green]✓ Package installed successfully[/green]")
                console.print(f"  Location: {installed_dir}")
                emit_template_installed_events(
                    vendor_id=vendor_id, product_id=None, method="local_file"
                )
                return

        # Install from API
        # Determine if this is vendor or product installation
        parts = vendor_or_product.split("/")

        if vendor or len(parts) == 1:
            # Vendor-level installation
            vendor_id = parts[0].lower()
            console.print(f"[cyan]Installing vendor package: {vendor_id}[/cyan]")

            # Verify vendor exists
            try:
                vendor_info = client.get_vendor_detail(vendor_id)
                vendor_name = vendor_info.get("vendor", vendor_id)
                products = vendor_info.get("products", [])
                console.print(f"[dim]Vendor: {vendor_name} ({len(products)} products)[/dim]")
            except CommunityAPINotFoundError:
                console.print(f"[red]Error: Vendor '{vendor_id}' not found[/red]")
                raise typer.Exit(code=1)

            # Download progress callback
            def progress_callback(bytes_downloaded: int, total_bytes: int):
                if total_bytes > 0:
                    percent = (bytes_downloaded / total_bytes) * 100
                    console.print(
                        f"\r[dim]Downloading: {bytes_downloaded:,} / {total_bytes:,} bytes ({percent:.1f}%)[/dim]",
                        end="",
                    )

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

            console.print("\n[green]✓ Vendor package installed successfully[/green]")
            console.print(f"  Location: {installed_dir}")
            console.print(
                "[dim]Configure generators in config.yaml to enable/disable individual templates[/dim]"
            )
            emit_template_installed_events(
                vendor_id=vendor_id, product_id=None, method="community_api"
            )

        elif product or len(parts) == 2:
            # Product-level installation
            vendor_id = parts[0].lower()
            product_id = parts[1].lower()
            console.print(f"[cyan]Installing product: {vendor_id}/{product_id}[/cyan]")

            # Verify product exists
            try:
                product_info = client.get_product_detail(vendor_id, product_id)
                product_name = product_info.get("product", product_id)
                collection_version = product_info.get("collection_version", "N/A")
                data_sources = product_info.get("data_sources", [])
                total_templates = _count_data_source_templates(data_sources)
                console.print(
                    f"[dim]Product: {product_name} (v{collection_version}, {total_templates} templates)[/dim]"
                )
            except CommunityAPINotFoundError:
                console.print(f"[red]Error: Product '{vendor_id}/{product_id}' not found[/red]")
                console.print(
                    f"[dim]Use 'meltr templates browse --vendor {vendor_id}' to see available products[/dim]"
                )
                raise typer.Exit(code=1)

            # Download progress callback
            def progress_callback(bytes_downloaded: int, total_bytes: int):
                if total_bytes > 0:
                    percent = (bytes_downloaded / total_bytes) * 100
                    console.print(
                        f"\r[dim]Downloading: {bytes_downloaded:,} / {total_bytes:,} bytes ({percent:.1f}%)[/dim]",
                        end="",
                    )

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

            console.print("\n[green]✓ Product installed successfully[/green]")
            console.print(f"  Location: {installed_dir}")
            console.print(
                "[dim]Configure generators in config.yaml to enable/disable individual templates[/dim]"
            )
            emit_template_installed_events(
                vendor_id=vendor_id, product_id=product_id, method="community_api"
            )

        else:
            # Invalid - too many parts (individual template not supported)
            console.print("[red]Error: Individual template installation not supported[/red]")
            console.print("[yellow]Install at product or vendor level:[/yellow]")
            if len(parts) >= 2:
                vendor_id = parts[0]
                product_id = parts[1]
                console.print(
                    f"[cyan]  Product: meltr templates install {vendor_id}/{product_id} --product[/cyan]"
                )
                console.print(
                    f"[cyan]  Vendor:  meltr templates install {vendor_id} --vendor[/cyan]"
                )
            else:
                console.print(
                    f"[cyan]  Vendor:  meltr templates install {parts[0]} --vendor[/cyan]"
                )
            console.print(
                "[dim]Individual templates are enabled/disabled via generator configuration[/dim]"
            )
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
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("install")
def templates_install(
    vendor_or_product: str | None = typer.Argument(
        None, help="Vendor ID (e.g., 'microsoft') or Product ID (e.g., 'microsoft/windows')"
    ),
    vendor: bool = typer.Option(False, "--vendor", help="Install all products from vendor"),
    product: bool = typer.Option(
        False, "--product", help="Install specific product (use vendor/product format)"
    ),
    list_vendors: bool = typer.Option(
        False, "--list-vendors", help="List available vendors to install"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="With --list-vendors, print vendors as JSON (for scripts)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive: reserved for future confirmation skips (install is non-interactive)",
    ),
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing installation"),
    local_file: Path | None = typer.Option(
        None, "--local-file", help="Install from local .forge file"
    ),
) -> None:
    """Install template packages from community registry or local package.

    Installation levels:
      - Vendor: Install all products for a vendor
        Example: meltr templates install microsoft --vendor

      - Product: Install a specific product (maintains collection.json integrity)
        Example: meltr templates install microsoft/windows --product
        Example: meltr templates install aws/cloudtrail --product

    Individual templates are enabled/disabled via generator configuration in config.yaml.
    """
    _ = yes  # Reserved for scripted parity; this command path does not prompt today.
    try:
        # Get API URL from config or parameter
        if api_url is None:
            config = load_config()
            api_url = config.templates.community_api_url

        client = CommunityAPIClient(base_url=api_url)

        # Handle --list-vendors option
        if list_vendors:
            try:
                # Use search_templates to get full hierarchy with product counts
                result = client.search_templates(page=1, page_size=100)
                vendors = result.get("vendors", [])

                if not vendors:
                    if json_output:
                        console.print(json.dumps({"vendors": []}))
                    else:
                        console.print("[yellow]No vendors found in registry[/yellow]")
                    return

                if json_output:
                    rows = []
                    for vendor_data in vendors:
                        vendor_id = vendor_data.get("id", "unknown")
                        products = vendor_data.get("products", [])
                        rows.append(
                            {
                                "id": vendor_id,
                                "vendor": vendor_data.get("vendor", vendor_id),
                                "product_count": len(products),
                                "install_vendor_cmd": f"meltr templates install {vendor_id} --vendor",
                            }
                        )
                    console.print(json.dumps({"vendors": rows}, indent=2))
                    return

                console.print("[cyan]Available Vendors:[/cyan]\n")
                for vendor_data in vendors:
                    vendor_id = vendor_data.get("id", "unknown")
                    vendor_name = vendor_data.get("vendor", vendor_id)
                    products = vendor_data.get("products", [])
                    product_count = len(products)

                    console.print(f"[bold cyan]{vendor_name}[/bold cyan] ([dim]{vendor_id}[/dim])")
                    console.print(f"  [green]{product_count} product(s)[/green]")
                    console.print(
                        f"  [dim]Install: meltr templates install {vendor_id} --vendor[/dim]\n"
                    )

                return
            except CommunityAPIError as e:
                console.print(f"[red]Error listing vendors: {e}[/red]")
                raise typer.Exit(code=1)

        # Require vendor_or_product if not listing
        if not vendor_or_product:
            console.print(
                "[red]Error: Must specify vendor or product ID, or use --list-vendors[/red]"
            )
            console.print(
                "[dim]Hint: Use 'meltr templates install --list-vendors' to see available vendors[/dim]"
            )
            console.print("[dim]Examples:[/dim]")
            console.print("[dim]  Vendor:  meltr templates install microsoft --vendor[/dim]")
            console.print(
                "[dim]  Product: meltr templates install microsoft/windows --product[/dim]"
            )
            raise typer.Exit(code=1)

        # Call core installation logic
        _do_install_template(
            vendor_or_product=vendor_or_product,
            vendor=vendor,
            product=product,
            api_url=api_url,
            overwrite=overwrite,
            local_file=local_file,
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("update")
def templates_update(
    vendor_id: str | None = typer.Argument(
        None, help="Vendor ID to update (all vendors if omitted)"
    ),
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check for updates without installing"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive: reserved for future confirmation skips (update does not prompt today)",
    ),
) -> None:
    """Update templates from community registry."""
    _ = yes
    try:
        config = load_config()
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / "default"

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
                d.name for d in default_path.iterdir() if d.is_dir() and not d.name.startswith(".")
            ]

        if not vendors_to_check:
            console.print("[yellow]No vendors to update[/yellow]")
            return

        console.print("[cyan]Checking for updates...[/cyan]\n")

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
                products = vendor_info.get("products", [])
                for product_id in products:
                    try:
                        product_info = client.get_product_detail(vendor_id, product_id)
                        remote_version = product_info.get("collection_version")

                        # Get local version
                        local_version = get_local_collection_version(
                            vendor_id, product_id, templates_path
                        )

                        if remote_version and compare_versions(local_version, remote_version) < 0:
                            updates_available.append(
                                {
                                    "vendor_id": vendor_id,
                                    "product_id": product_id,
                                    "local_version": local_version,
                                    "remote_version": remote_version,
                                }
                            )

                            status = format_version_status(local_version, remote_version)
                            console.print(f"[yellow]{vendor_id}/{product_id}:[/yellow] {status}")
                        elif remote_version:
                            status = format_version_status(local_version, remote_version)
                            console.print(f"[dim]{vendor_id}/{product_id}:[/dim] {status}")

                    except CommunityAPINotFoundError:
                        console.print(
                            f"[dim]Skipping {vendor_id}/{product_id}: not found in registry[/dim]"
                        )
                        continue
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Failed to check {vendor_id}/{product_id}: {e}[/yellow]"
                        )
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
            console.print(
                f"\n[yellow]Dry run: {len(updates_available)} update(s) available[/yellow]"
            )
            console.print("[dim]Run without --dry-run to install updates[/dim]")
            return

        # Group updates by vendor
        vendor_updates = {}
        for update in updates_available:
            vendor_id = update["vendor_id"]
            if vendor_id not in vendor_updates:
                vendor_updates[vendor_id] = []
            vendor_updates[vendor_id].append(update)

        # Install updates
        console.print(f"\n[cyan]Installing {len(updates_available)} update(s)...[/cyan]\n")

        for vendor_id, updates in vendor_updates.items():
            console.print(f"[cyan]Updating {vendor_id}...[/cyan]")

            try:
                download_and_install_vendor(
                    client=client,
                    vendor_id=vendor_id,
                    target_dir=default_path,
                    overwrite=True,  # Always overwrite for updates
                    backup_count=config.templates.backup_count,
                )

                console.print(f"[green]✓ Updated {vendor_id}[/green]")

                for update in updates:
                    console.print(
                        f"  {update['product_id']}: {update['local_version']} → {update['remote_version']}"
                    )

            except Exception as e:
                console.print(f"[red]Failed to update {vendor_id}: {e}[/red]")
                continue

        console.print("\n[green]Update complete[/green]")

    except CommunityAPIError as e:
        console.print(f"[red]API error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("compare")
def templates_compare(
    api_url: str | None = typer.Option(
        None, "--api-url", envvar="MELTR_COMMUNITY_API_URL", help="Community API URL"
    ),
    page: int = typer.Option(1, "--page", help="Page number (for paginated output)"),
    page_size: int = typer.Option(20, "--page-size", help="Results per page"),
) -> None:
    """Compare local templates with remote registry (show installed, available, updates)."""
    try:
        config = load_config()
        templates_path = Path(config.templates.local_path)
        default_path = templates_path / "default"

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
            vendor_id = vendor_data.get("id")
            products = vendor_data.get("products", [])

            for product_id in products:
                try:
                    product_info = client.get_product_detail(vendor_id, product_id)
                    data_sources = product_info.get("data_sources", [])

                    for ds_data in data_sources:
                        templates = ds_data.get("templates", []) or ds_data.get("event_types", [])
                        for template in templates:
                            template_id = template.get("id")
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

        console.print("\n[bold]Template Comparison[/bold]\n")
        console.print(f"  [green]Installed locally:[/green] {len(local_template_ids)} templates")
        console.print(f"  [cyan]Available remotely:[/cyan] {len(remote_template_ids)} templates")
        console.print(f"  [yellow]Installed & up to date:[/yellow] {len(both)} templates")

        if only_local:
            sorted_local = sorted(only_local)
            total_pages = (len(sorted_local) + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, len(sorted_local))
            page_items = sorted_local[start_idx:end_idx]

            console.print(
                f"\n[dim]Templates installed locally but not in registry ({len(only_local)} total):[/dim]"
            )
            for tid in page_items:
                console.print(f"  • {tid}")

            if total_pages > 1:
                console.print(
                    f"\n[dim]Page {page} of {total_pages} (showing {len(page_items)} of {len(sorted_local)})[/dim]"
                )
                if page < total_pages:
                    console.print(f"[dim]Use --page {page + 1} to see more[/dim]")

        if only_remote:
            console.print(
                f"\n[dim]Templates available remotely but not installed ({len(only_remote)}):[/dim]"
            )
            console.print(
                "  [dim]Use 'meltr templates search' or 'meltr templates browse' to discover them[/dim]"
            )

        # Check for vendors installed locally
        if default_path.exists():
            local_vendors = {
                d.name for d in default_path.iterdir() if d.is_dir() and not d.name.startswith(".")
            }
            console.print(f"\n[bold]Installed Vendors:[/bold] {', '.join(sorted(local_vendors))}")

        console.print(
            f"\n[bold]Available Vendors in Registry:[/bold] {', '.join(sorted(remote_vendor_products.keys()))}"
        )
        console.print("\n[dim]Use 'meltr templates update' to check for updates[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("diff")
def templates_diff(
    template_id: str = typer.Argument(
        ...,
        help="Template ID: vendor/product/data_source/template_name",
    ),
    include_meta: bool = typer.Option(
        True,
        "--meta/--no-meta",
        help="Include .meta.yaml when both default and custom metadata files exist",
    ),
) -> None:
    """Unified diff: installed default copy vs your custom copy (requires customized template)."""
    try:
        config = load_config()
        loader = TemplateLoader(config)
        default_pair = loader.resolve_paths_under(loader.default_path, template_id)
        if not default_pair:
            console.print(
                f"[red]Template not found under default:[/red] [cyan]{template_id}[/cyan]"
            )
            raise typer.Exit(code=1)
        custom_pair = loader.resolve_paths_under(loader.custom_path, template_id)
        if not custom_pair:
            console.print(
                "[yellow]No custom template on disk.[/yellow] Run "
                f"[cyan]meltr templates customize {template_id}[/cyan] first."
            )
            raise typer.Exit(code=1)

        d_j2, d_meta = default_pair
        c_j2, c_meta = custom_pair
        any_diff = False
        label_base = template_id
        if _print_unified_diff_file(
            d_j2,
            c_j2,
            f"default/{label_base}.j2",
            f"custom/{label_base}.j2",
        ):
            any_diff = True
        else:
            console.print(f"[green].j2 identical[/green] [dim]({label_base}.j2)[/dim]")

        if include_meta and d_meta.is_file() and c_meta.is_file():
            if _print_unified_diff_file(
                d_meta,
                c_meta,
                f"default/{label_base}.meta.yaml",
                f"custom/{label_base}.meta.yaml",
            ):
                any_diff = True
            else:
                console.print(f"[green].meta.yaml identical[/green] [dim]({label_base})[/dim]")
        elif include_meta and (d_meta.is_file() ^ c_meta.is_file()):
            console.print(
                "[yellow]Metadata present on only one side; skipping .meta.yaml diff "
                "(use templates merge to sync from default).[/yellow]"
            )

        if not any_diff:
            console.print("\n[bold green]No differences[/bold green] between default and custom.")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("merge")
def templates_merge(
    template_id: str = typer.Argument(
        ...,
        help="Template ID: vendor/product/data_source/template_name",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive: overwrite custom from default without confirming",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="If no custom template exists, create it by copying from default (like customize)",
    ),
) -> None:
    """Copy default .j2 (+ .meta.yaml when present) over custom; backs up prior custom files."""
    try:
        config = load_config()
        loader = TemplateLoader(config)
        default_pair = loader.resolve_paths_under(loader.default_path, template_id)
        if not default_pair:
            console.print(
                f"[red]Template not found under default:[/red] [cyan]{template_id}[/cyan]"
            )
            raise typer.Exit(code=1)
        d_j2, d_meta = default_pair

        custom_pair = loader.resolve_paths_under(loader.custom_path, template_id)
        parts = [p for p in template_id.strip().strip("/").split("/") if p]
        if len(parts) != 4:
            console.print(
                "[red]Template ID must have four segments: vendor/product/data_source/name[/red]"
            )
            raise typer.Exit(code=1)
        v, prod, ds, name = parts

        if custom_pair:
            c_j2, c_meta = custom_pair
        elif force:
            c_dir = loader.custom_path / v / prod / ds
            c_dir.mkdir(parents=True, exist_ok=True)
            c_j2 = c_dir / f"{name}.j2"
            c_meta = c_dir / f"{name}.meta.yaml"
        else:
            console.print(
                "[yellow]No custom template.[/yellow] Run "
                f"[cyan]meltr templates customize {template_id}[/cyan] "
                "or pass [cyan]--force[/cyan]."
            )
            raise typer.Exit(code=1)

        had_custom = c_j2.is_file()
        if had_custom and not yes:
            if not Confirm.ask(
                f"Overwrite custom files for [cyan]{template_id}[/cyan] from default? "
                "(Previous custom files will be backed up.)",
                default=False,
            ):
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(code=0)

        home = get_logforge_home()
        if had_custom:
            bdir = _backup_custom_template_files(home, template_id, c_j2, c_meta)
            console.print(f"[dim]Backed up prior custom files to {bdir}[/dim]")

        shutil.copy2(d_j2, c_j2)
        if d_meta.is_file():
            shutil.copy2(d_meta, c_meta)
        console.print(
            f"[green]✓ Custom template synced from default:[/green] [cyan]{template_id}[/cyan]"
        )
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("create")
def templates_create(
    template_id: str = typer.Argument(
        ...,
        help="Four-part ID: vendor/product/data_source/template_name (files go under templates/custom/)",
    ),
    description: str = typer.Option(
        "Custom MELTr template",
        "--description",
        "-d",
        help="Metadata description",
    ),
    output_format: str = typer.Option(
        "JSON",
        "--format",
        "-f",
        help="Metadata output format (JSON, XML, CSV, … — same as metadata schema)",
    ),
    force: bool = typer.Option(False, "--force", help="Replace existing custom .j2 / .meta.yaml"),
) -> None:
    """Create a minimal custom template (.j2 + .meta.yaml) under templates/custom/."""
    try:
        parts = [p for p in template_id.strip().strip("/").split("/") if p]
        if len(parts) != 4:
            console.print(
                "[red]Template ID must have four segments: vendor/product/data_source/name[/red]"
            )
            raise typer.Exit(code=1)
        v, prod, data_source, t_name = parts

        try:
            meta_model = TemplateMetadata(
                vendor=v,
                product=prod,
                data_source=data_source,
                description=description,
                format=output_format,
                is_generator=True,
            )
        except Exception as e:
            console.print(f"[red]Invalid metadata: {e}[/red]")
            raise typer.Exit(code=1)

        config = load_config()
        loader = TemplateLoader(config)
        c_dir = loader.custom_path / v / prod / data_source
        c_j2 = c_dir / f"{t_name}.j2"
        c_meta = c_dir / f"{t_name}.meta.yaml"

        if (c_j2.is_file() or c_meta.is_file()) and not force:
            console.print(
                f"[red]Already exists:[/red] [cyan]{template_id}[/cyan]. "
                "Use [cyan]--force[/cyan] to overwrite."
            )
            raise typer.Exit(code=1)

        c_dir.mkdir(parents=True, exist_ok=True)
        skel = f"{{# MELTr: {template_id} #}}\n" '{{ {"message": "example"} | tojson }}\n'
        c_j2.write_text(skel, encoding="utf-8")
        with c_meta.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                meta_model.model_dump(mode="json", exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

        val = validate_template(c_j2, c_meta)
        if val.errors:
            for err in val.errors:
                console.print(f"[yellow]Validation: {err}[/yellow]")
        if val.warnings:
            for warn in val.warnings:
                console.print(f"[dim]Validation warning: {warn}[/dim]")

        console.print(f"[green]✓ Created custom template[/green] [cyan]{template_id}[/cyan]")
        console.print(f"  [dim]{c_j2}[/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
