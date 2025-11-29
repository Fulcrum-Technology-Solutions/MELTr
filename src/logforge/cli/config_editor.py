"""Interactive configuration editor assistant."""

from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt, FloatPrompt
from rich.table import Table

from logforge.core.config import (
    Config,
    OutputDefinition,
    OutputRotationConfig,
    GeneratorConfig,
    load_config,
    save_config as save_config_file,
)
from logforge.core.paths import get_logforge_home
from logforge.templates.loader import TemplateLoader

console = Console()


def config_editor(
    section: Optional[str] = None,
    edit_existing: bool = True,
) -> None:
    """Interactive configuration editor.
    
    Args:
        section: Specific section to edit (outputs, generators, etc.)
        edit_existing: If True, load existing config; if False, start fresh
    """
    try:
        if edit_existing:
            config = load_config()
            console.print("[green]Loaded existing configuration[/green]\n")
        else:
            from logforge.core.config import create_default_config
            home = get_logforge_home()
            config = create_default_config(home)
            console.print("[green]Starting with default configuration[/green]\n")
    except FileNotFoundError:
        console.print("[yellow]No existing config found. Starting fresh.[/yellow]\n")
        from logforge.core.config import create_default_config
        home = get_logforge_home()
        config = create_default_config(home)
    
    if section:
        # Edit specific section
        if section == "outputs":
            config = _edit_outputs_section(config)
        elif section == "generators":
            config = _edit_generators_section(config)
        elif section == "api":
            config = _edit_api_section(config)
        elif section == "engine":
            config = _edit_engine_section(config)
        elif section == "logging":
            config = _edit_logging_section(config)
        else:
            console.print(f"[red]Unknown section: {section}[/red]")
            console.print("[yellow]Available sections: outputs, generators, api, engine, logging[/yellow]")
            return
    else:
        # Main menu
        while True:
            choice = _show_main_menu()
            
            if choice == "1":
                config = _edit_outputs_section(config)
            elif choice == "2":
                config = _edit_generators_section(config)
            elif choice == "3":
                config = _edit_api_section(config)
            elif choice == "4":
                config = _edit_engine_section(config)
            elif choice == "5":
                config = _edit_logging_section(config)
            elif choice == "6":
                _preview_config(config)
            elif choice == "7":
                if _save_config(config):
                    console.print("\n[green]✓ Configuration saved successfully![/green]")
                    break
            elif choice == "8":
                if Confirm.ask("\n[yellow]Discard changes and exit?", default=False):
                    break
            else:
                console.print("[red]Invalid choice[/red]")
    
    console.print("\n[dim]Configuration editor closed[/dim]")


def _show_main_menu() -> str:
    """Display main configuration menu."""
    console.print("\n[bold]LogForge Configuration Editor[/bold]\n")
    
    menu = Panel(
        "[cyan]1.[/cyan] Manage Outputs\n"
        "[cyan]2.[/cyan] Manage Generators\n"
        "[cyan]3.[/cyan] API Settings\n"
        "[cyan]4.[/cyan] Engine Settings\n"
        "[cyan]5.[/cyan] Logging Settings\n"
        "[cyan]6.[/cyan] Preview Configuration\n"
        "[cyan]7.[/cyan] Save and Exit\n"
        "[cyan]8.[/cyan] Exit Without Saving",
        title="Main Menu",
        border_style="blue",
    )
    console.print(menu)
    
    return Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="7")


def _edit_outputs_section(config: Config) -> Config:
    """Edit outputs section interactively."""
    console.print("\n[bold]Output Management[/bold]\n")
    
    while True:
        # Show current outputs
        if config.outputs.definitions:
            table = Table(title="Current Outputs")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Details", style="yellow")
            
            for output in config.outputs.definitions:
                details = []
                if output.type == "file" and output.path:
                    details.append(f"path: {output.path}")
                elif output.type == "http" and output.url:
                    details.append(f"url: {output.url}")
                elif output.type == "tcp" and output.host:
                    details.append(f"{output.host}:{output.port}")
                elif output.type == "console":
                    details.append(f"stream: {output.stream or 'stdout'}")
                
                table.add_row(output.name, output.type, ", ".join(details))
            
            console.print(table)
        else:
            console.print("[yellow]No outputs configured[/yellow]\n")
        
        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add new output")
        if config.outputs.definitions:
            console.print("  [2] Edit output")
            console.print("  [3] Remove output")
        console.print("  [4] Configure retry settings")
        console.print("  [5] Configure buffer size")
        console.print("  [6] Back to main menu")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5", "6"], default="6")
        
        if choice == "1":
            new_output = _create_output_interactive()
            if new_output:
                config.outputs.definitions.append(new_output)
                console.print(f"[green]✓ Added output: {new_output.name}[/green]")
        elif choice == "2" and config.outputs.definitions:
            config = _edit_output_interactive(config)
        elif choice == "3" and config.outputs.definitions:
            config = _remove_output_interactive(config)
        elif choice == "4":
            config = _edit_retry_config(config)
        elif choice == "5":
            config = _edit_buffer_size(config)
        elif choice == "6":
            break
    
    return config


def _create_output_interactive() -> Optional[OutputDefinition]:
    """Interactively create a new output definition."""
    console.print("\n[bold]Create New Output[/bold]\n")
    
    # Output name
    name = Prompt.ask("Output name", default="output-1")
    
    # Output type
    console.print("\n[cyan]Output Types:[/cyan]")
    console.print("  [1] file - Write to file")
    console.print("  [2] console - Write to stdout/stderr")
    console.print("  [3] http - Send via HTTP POST")
    console.print("  [4] tcp - Send via TCP socket")
    console.print("  [5] syslog - Send via Syslog")
    
    type_choice = Prompt.ask("\nSelect output type", choices=["1", "2", "3", "4", "5"], default="1")
    type_map = {
        "1": "file",
        "2": "console",
        "3": "http",
        "4": "tcp",
        "5": "syslog",
    }
    output_type = type_map[type_choice]
    
    # Type-specific configuration
    if output_type == "file":
        return _create_file_output(name)
    elif output_type == "console":
        return _create_console_output(name)
    elif output_type == "http":
        return _create_http_output(name)
    elif output_type == "tcp":
        return _create_tcp_output(name)
    elif output_type == "syslog":
        return _create_syslog_output(name)
    
    return None


def _create_file_output(name: str) -> OutputDefinition:
    """Create file output interactively."""
    home = get_logforge_home()
    default_path = f"${{LOGFORGE_HOME}}/outputs/{{generator}}-{{date}}.log"
    
    path = Prompt.ask(
        "File path (supports variables: {generator}, {date}, {hour}, {vendor}, {product})",
        default=default_path,
    )
    
    # Rotation settings
    rotation = None
    if Confirm.ask("\nConfigure file rotation?", default=True):
        rotation_type = Prompt.ask(
            "Rotation type",
            choices=["size", "time"],
            default="size",
        )
        
        if rotation_type == "size":
            max_size_str = Prompt.ask(
                "Max file size (e.g., 100MB, 1GB)",
                default="100MB",
            )
            # Convert to bytes (simplified - just store as string, validation happens later)
            max_size = max_size_str
        else:
            max_size = None
        
        max_age = None
        if rotation_type == "time":
            max_age = Prompt.ask(
                "Max age (e.g., 7d, 24h, 1w)",
                default="7d",
            )
        
        max_files = IntPrompt.ask(
            "Maximum rotated files to keep",
            default=10,
        )
        
        compress = Confirm.ask("Compress rotated files?", default=True)
        
        rotation = OutputRotationConfig(
            type=rotation_type,
            max_size=max_size if max_size else None,
            max_age=max_age,
            max_files=max_files,
            compress=compress,
        )
    
    return OutputDefinition(
        name=name,
        type="file",
        path=path,
        rotation=rotation,
    )


def _create_console_output(name: str) -> OutputDefinition:
    """Create console output interactively."""
    stream = Prompt.ask(
        "Stream",
        choices=["stdout", "stderr"],
        default="stdout",
    )
    
    format_type = Prompt.ask(
        "Format",
        choices=["json", "text"],
        default="json",
    )
    
    return OutputDefinition(
        name=name,
        type="console",
        stream=stream,
        format=format_type,
    )


def _create_http_output(name: str) -> OutputDefinition:
    """Create HTTP output interactively."""
    url = Prompt.ask("HTTP URL", default="https://api.example.com/v1/events")
    
    method = Prompt.ask(
        "HTTP method",
        choices=["POST", "PUT", "PATCH"],
        default="POST",
    )
    
    # Headers
    headers = {}
    if Confirm.ask("Add authentication header?", default=True):
        auth_type = Prompt.ask(
            "Authentication type",
            choices=["Bearer", "Splunk HEC", "API Key"],
            default="Bearer",
        )
        
        if auth_type == "Bearer":
            token_var = Prompt.ask(
                "Token environment variable name",
                default="API_TOKEN",
            )
            headers["Authorization"] = f"Bearer ${{{token_var}}}"
        elif auth_type == "Splunk HEC":
            token_var = Prompt.ask(
                "HEC token environment variable name",
                default="SPLUNK_HEC_TOKEN",
            )
            headers["Authorization"] = f"Splunk ${{{token_var}}}"
        else:  # API Key
            header_name = Prompt.ask("API key header name", default="X-API-Key")
            token_var = Prompt.ask(
                "API key environment variable name",
                default="API_KEY",
            )
            headers[header_name] = f"${{{token_var}}}"
    
    # Add Content-Type
    headers["Content-Type"] = "application/json"
    
    # Batching
    batch_size = IntPrompt.ask("Batch size (events per batch)", default=100)
    batch_interval = IntPrompt.ask("Batch interval (seconds)", default=5)
    timeout = IntPrompt.ask("Request timeout (seconds)", default=30)
    
    return OutputDefinition(
        name=name,
        type="http",
        url=url,
        method=method,
        headers=headers,
        batch_size=batch_size,
        batch_interval=batch_interval,
        timeout=timeout,
    )


def _create_tcp_output(name: str) -> OutputDefinition:
    """Create TCP output interactively."""
    host = Prompt.ask("Host", default="localhost")
    port = IntPrompt.ask("Port", default=514)
    
    delimiter = Prompt.ask(
        "Delimiter",
        default="\\n",
    )
    
    keepalive = Confirm.ask("Enable TCP keepalive?", default=True)
    
    return OutputDefinition(
        name=name,
        type="tcp",
        host=host,
        port=port,
        delimiter=delimiter,
        keepalive=keepalive,
    )


def _create_syslog_output(name: str) -> OutputDefinition:
    """Create Syslog output interactively."""
    host = Prompt.ask("Syslog server host", default="localhost")
    port = IntPrompt.ask("Port", default=514)
    
    protocol = Prompt.ask(
        "Protocol",
        choices=["tcp", "udp"],
        default="udp",
    )
    
    facility = Prompt.ask(
        "Facility",
        choices=["kern", "user", "mail", "daemon", "auth", "syslog", "lpr", "news", "uucp", "cron", "authpriv", "ftp", "local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7"],
        default="user",
    )
    
    severity = Prompt.ask(
        "Severity",
        choices=["emerg", "alert", "crit", "err", "warning", "notice", "info", "debug"],
        default="info",
    )
    
    return OutputDefinition(
        name=name,
        type="syslog",
        host=host,
        port=port,
        protocol=protocol,
        facility=facility,
        severity=severity,
    )


def _edit_output_interactive(config: Config) -> Config:
    """Edit an existing output."""
    if not config.outputs.definitions:
        console.print("[yellow]No outputs to edit[/yellow]")
        return config
    
    # List outputs
    console.print("\n[bold]Select Output to Edit[/bold]\n")
    for i, output in enumerate(config.outputs.definitions, 1):
        console.print(f"  [{i}] {output.name} ({output.type})")
    
    choice = IntPrompt.ask("\nSelect output number", default=1)
    if choice < 1 or choice > len(config.outputs.definitions):
        console.print("[red]Invalid selection[/red]")
        return config
    
    output = config.outputs.definitions[choice - 1]
    console.print(f"\n[bold]Editing: {output.name}[/bold]\n")
    
    # For now, just show current config and allow basic edits
    # Full editing would require re-creating the output
    console.print("[yellow]Note: Full output editing not yet implemented.[/yellow]")
    console.print("[yellow]Remove and re-add the output to change settings.[/yellow]")
    
    return config


def _remove_output_interactive(config: Config) -> Config:
    """Remove an output."""
    if not config.outputs.definitions:
        console.print("[yellow]No outputs to remove[/yellow]")
        return config
    
    # List outputs
    console.print("\n[bold]Select Output to Remove[/bold]\n")
    for i, output in enumerate(config.outputs.definitions, 1):
        console.print(f"  [{i}] {output.name} ({output.type})")
    
    choice = IntPrompt.ask("\nSelect output number", default=1)
    if choice < 1 or choice > len(config.outputs.definitions):
        console.print("[red]Invalid selection[/red]")
        return config
    
    output = config.outputs.definitions[choice - 1]
    
    if Confirm.ask(f"\n[yellow]Remove output '{output.name}'?", default=False):
        config.outputs.definitions.pop(choice - 1)
        console.print(f"[green]✓ Removed output: {output.name}[/green]")
        
        # Check if any generators use this output
        for gen in config.generators:
            if output.name in gen.outputs:
                console.print(f"[yellow]Warning: Generator '{gen.name}' uses this output[/yellow]")
    
    return config


def _edit_retry_config(config: Config) -> Config:
    """Edit retry configuration."""
    console.print("\n[bold]Retry Configuration[/bold]\n")
    
    retry = config.outputs.retry
    
    max_attempts_str = Prompt.ask(
        "Max retry attempts (-1 for unlimited)",
        default=str(retry.max_attempts),
    )
    try:
        max_attempts = int(max_attempts_str)
    except ValueError:
        max_attempts = -1
    
    retry_interval = IntPrompt.ask(
        "Retry interval (seconds)",
        default=retry.retry_interval,
    )
    
    backoff_multiplier = FloatPrompt.ask(
        "Backoff multiplier",
        default=retry.backoff_multiplier,
    )
    
    max_backoff = IntPrompt.ask(
        "Max backoff (seconds)",
        default=retry.max_backoff,
    )
    
    from logforge.core.config import RetryConfig
    config.outputs.retry = RetryConfig(
        max_attempts=max_attempts,
        retry_interval=retry_interval,
        backoff_multiplier=backoff_multiplier,
        max_backoff=max_backoff,
    )
    
    console.print("[green]✓ Retry configuration updated[/green]")
    return config


def _edit_buffer_size(config: Config) -> Config:
    """Edit buffer size."""
    console.print("\n[bold]Buffer Size Configuration[/bold]\n")
    
    buffer_size = IntPrompt.ask(
        "Event buffer size",
        default=config.outputs.buffer_size,
    )
    
    config.outputs.buffer_size = buffer_size
    console.print(f"[green]✓ Buffer size set to {buffer_size}[/green]")
    return config


def _edit_generators_section(config: Config) -> Config:
    """Edit generators section interactively."""
    console.print("\n[bold]Generator Management[/bold]\n")
    
    while True:
        # Show current generators
        if config.generators:
            table = Table(title="Current Generators")
            table.add_column("Name", style="cyan")
            table.add_column("Template", style="green")
            table.add_column("Enabled", style="yellow")
            table.add_column("Rate", style="magenta")
            table.add_column("Outputs", style="blue")
            
            for gen in config.generators:
                # Rate comes from template metadata
                rate = "from template"
                outputs_str = ", ".join(gen.outputs) if gen.outputs else "none"
                table.add_row(
                    gen.name,
                    gen.template,
                    "✓" if gen.enabled else "✗",
                    rate,
                    outputs_str,
                )
            
            console.print(table)
        else:
            console.print("[yellow]No generators configured[/yellow]\n")
        
        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add new generator")
        if config.generators:
            console.print("  [2] Edit generator")
            console.print("  [3] Remove generator")
        console.print("  [4] Back to main menu")
        
        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            new_gen = _create_generator_interactive(config)
            if new_gen:
                config.generators.append(new_gen)
                console.print(f"[green]✓ Added generator: {new_gen.name}[/green]")
        elif choice == "2" and config.generators:
            config = _edit_generator_interactive(config)
        elif choice == "3" and config.generators:
            config = _remove_generator_interactive(config)
        elif choice == "4":
            break
    
    return config


def _create_generator_interactive(config: Config) -> Optional[GeneratorConfig]:
    """Interactively create a new generator."""
    console.print("\n[bold]Create New Generator[/bold]\n")
    
    # Generator name
    name = Prompt.ask("Generator name", default="generator-1")
    
    # Check if name already exists
    if any(g.name == name for g in config.generators):
        console.print(f"[red]Generator '{name}' already exists[/red]")
        if not Confirm.ask("Use a different name?", default=True):
            return None
        name = Prompt.ask("Generator name")
    
    # Template selection
    template = _select_template_interactive(config)
    if not template:
        console.print("[yellow]No template selected, cancelling[/yellow]")
        return None
    
    # Output selection
    if not config.outputs.definitions:
        console.print("[yellow]No outputs configured. Please add outputs first.[/yellow]")
        return None
    
    console.print("\n[bold]Select Outputs[/bold]\n")
    for i, output in enumerate(config.outputs.definitions, 1):
        console.print(f"  [{i}] {output.name} ({output.type})")
    
    output_choices = Prompt.ask(
        "\nSelect output numbers (comma-separated, e.g., 1,2)",
    )
    
    try:
        indices = [int(x.strip()) - 1 for x in output_choices.split(",")]
        selected_outputs = [config.outputs.definitions[i].name for i in indices if 0 <= i < len(config.outputs.definitions)]
    except (ValueError, IndexError):
        console.print("[red]Invalid output selection[/red]")
        return None
    
    if not selected_outputs:
        console.print("[red]No valid outputs selected[/red]")
        return None
    
    # Frequency comes from template metadata
    console.print("\n[bold]Frequency Configuration[/bold]\n")
    console.print("[green]✓ Frequency will be read from template metadata (.meta.yaml)[/green]")
    console.print("[dim]To customize frequency, copy template to custom/ directory and edit .meta.yaml[/dim]")
    
    enabled = Confirm.ask("\nEnable generator?", default=True)
    
    return GeneratorConfig(
        name=name,
        template=template,
        enabled=enabled,
        outputs=selected_outputs,
    )


def _select_template_interactive(config: Config) -> Optional[str]:
    """Interactively select a template."""
    console.print("\n[bold]Template Selection[/bold]\n")
    
    try:
        loader = TemplateLoader(config)
        templates = loader.discover_templates()
        
        if not templates:
            console.print("[yellow]No templates found. Install templates first.[/yellow]")
            return None
        
        # Group by vendor/product
        grouped = {}
        for template_id, template_info in templates.items():
            vendor = template_info.vendor
            product = template_info.product
            key = f"{vendor}/{product}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append((template_id, template_info))
        
        # Display grouped templates
        console.print("[cyan]Available Templates:[/cyan]\n")
        all_templates = []
        idx = 1
        for vendor_product, template_list in sorted(grouped.items()):
            console.print(f"[bold]{vendor_product}[/bold]")
            for template_id, template_info in sorted(template_list):
                metadata = template_info.metadata
                desc = metadata.description if metadata else ""
                desc_short = desc[:50] + "..." if len(desc) > 50 else desc
                console.print(f"  [{idx}] {template_id}")
                if desc_short:
                    console.print(f"      {desc_short}")
                all_templates.append(template_id)
                idx += 1
            console.print()
        
        choice = IntPrompt.ask("\nSelect template number", default=1)
        if choice < 1 or choice > len(all_templates):
            console.print("[red]Invalid selection[/red]")
            return None
        
        selected = all_templates[choice - 1]
        console.print(f"[green]Selected: {selected}[/green]")
        return selected
        
    except Exception as e:
        console.print(f"[red]Error loading templates: {e}[/red]")
        # Fallback: manual entry
        template = Prompt.ask("\nEnter template ID manually (e.g., paloalto/wildfire/threats/wildfire_threat_detected)")
        return template


def _edit_generator_interactive(config: Config) -> Config:
    """Edit an existing generator."""
    if not config.generators:
        console.print("[yellow]No generators to edit[/yellow]")
        return config
    
    # List generators
    console.print("\n[bold]Select Generator to Edit[/bold]\n")
    for i, gen in enumerate(config.generators, 1):
        console.print(f"  [{i}] {gen.name} ({gen.template})")
    
    choice = IntPrompt.ask("\nSelect generator number", default=1)
    if choice < 1 or choice > len(config.generators):
        console.print("[red]Invalid selection[/red]")
        return config
    
    gen = config.generators[choice - 1]
    console.print(f"\n[bold]Editing: {gen.name}[/bold]\n")
    
    # Edit enabled status
    enabled = Confirm.ask("Enable generator?", default=gen.enabled)
    gen.enabled = enabled
    
    # Frequency comes from template metadata
    console.print("\n[dim]Frequency is read from template metadata (.meta.yaml)[/dim]")
    console.print("[dim]To customize, copy template to custom/ directory and edit .meta.yaml[/dim]")
    
    # Edit outputs
    if Confirm.ask("Edit outputs?", default=False):
        console.print("\n[bold]Current outputs:[/bold] {}\n".format(", ".join(gen.outputs)))
        console.print("[cyan]Available outputs:[/cyan]")
        for i, output in enumerate(config.outputs.definitions, 1):
            console.print(f"  [{i}] {output.name} ({output.type})")
        
        output_choices = Prompt.ask(
            "\nSelect output numbers (comma-separated)",
            default=",".join(str(i+1) for i, o in enumerate(config.outputs.definitions) if o.name in gen.outputs),
        )
        
        try:
            indices = [int(x.strip()) - 1 for x in output_choices.split(",")]
            gen.outputs = [config.outputs.definitions[i].name for i in indices if 0 <= i < len(config.outputs.definitions)]
        except (ValueError, IndexError):
            console.print("[red]Invalid output selection[/red]")
    
    console.print("[green]✓ Generator updated[/green]")
    return config


def _remove_generator_interactive(config: Config) -> Config:
    """Remove a generator."""
    if not config.generators:
        console.print("[yellow]No generators to remove[/yellow]")
        return config
    
    # List generators
    console.print("\n[bold]Select Generator to Remove[/bold]\n")
    for i, gen in enumerate(config.generators, 1):
        console.print(f"  [{i}] {gen.name} ({gen.template})")
    
    choice = IntPrompt.ask("\nSelect generator number", default=1)
    if choice < 1 or choice > len(config.generators):
        console.print("[red]Invalid selection[/red]")
        return config
    
    gen = config.generators[choice - 1]
    
    if Confirm.ask(f"\n[yellow]Remove generator '{gen.name}'?", default=False):
        config.generators.pop(choice - 1)
        console.print(f"[green]✓ Removed generator: {gen.name}[/green]")
    
    return config


def _edit_api_section(config: Config) -> Config:
    """Edit API settings."""
    console.print("\n[bold]API Settings[/bold]\n")
    
    enabled = Confirm.ask("Enable API server?", default=config.api.enabled)
    config.api.enabled = enabled
    
    if enabled:
        host = Prompt.ask("API host", default=config.api.host)
        config.api.host = host
        
        port = IntPrompt.ask("API port", default=config.api.port)
        config.api.port = port
        
        auth_enabled = Confirm.ask("Enable API authentication?", default=config.api.auth.enabled)
        config.api.auth.enabled = auth_enabled
        
        if auth_enabled and not config.api.auth.key:
            console.print("[yellow]API key will be auto-generated on first start[/yellow]")
    
    console.print("[green]✓ API settings updated[/green]")
    return config


def _edit_engine_section(config: Config) -> Config:
    """Edit engine settings."""
    console.print("\n[bold]Engine Settings[/bold]\n")
    
    max_generators_str = Prompt.ask(
        "Max concurrent generators (empty for unlimited)",
        default=str(config.engine.max_generators) if config.engine.max_generators else "",
    )
    if max_generators_str:
        try:
            config.engine.max_generators = int(max_generators_str)
        except ValueError:
            config.engine.max_generators = None
    else:
        config.engine.max_generators = None
    
    thread_pool_str = Prompt.ask(
        "Thread pool size (empty for auto)",
        default=str(config.engine.thread_pool_size) if config.engine.thread_pool_size else "",
    )
    if thread_pool_str:
        try:
            config.engine.thread_pool_size = int(thread_pool_str)
        except ValueError:
            config.engine.thread_pool_size = None
    else:
        config.engine.thread_pool_size = None
    
    log_level = Prompt.ask(
        "Engine log level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=config.engine.log_level,
    )
    config.engine.log_level = log_level
    
    console.print("[green]✓ Engine settings updated[/green]")
    return config


def _edit_logging_section(config: Config) -> Config:
    """Edit logging settings."""
    console.print("\n[bold]Logging Settings[/bold]\n")
    
    level = Prompt.ask(
        "Log level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=config.logging.level,
    )
    config.logging.level = level
    
    log_file = Prompt.ask(
        "Log file path (empty for no file logging)",
        default=config.logging.file or "",
    )
    config.logging.file = log_file if log_file else None
    
    if config.logging.file:
        if Confirm.ask("Configure log rotation?", default=True):
            max_size_str = Prompt.ask(
                "Max log file size (e.g., 50MB)",
                default="50MB",
            )
            backup_count = IntPrompt.ask(
                "Number of backup files",
                default=config.logging.rotation.backup_count if config.logging.rotation else 5,
            )
            
            from logforge.core.config import RotationConfig
            config.logging.rotation = RotationConfig(
                max_size=max_size_str,
                backup_count=backup_count,
            )
    
    console.print("[green]✓ Logging settings updated[/green]")
    return config


def _preview_config(config: Config) -> None:
    """Preview current configuration."""
    console.print("\n[bold]Configuration Preview[/bold]\n")
    
    import yaml
    config_dict = config.model_dump(mode='json', exclude_none=True)
    output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    
    from rich.syntax import Syntax
    syntax = Syntax(output, "yaml", theme="monokai")
    console.print(syntax)


def _save_config(config: Config) -> bool:
    """Save configuration with confirmation."""
    _preview_config(config)
    
    if not Confirm.ask("\n[yellow]Save this configuration?", default=True):
        return False
    
    try:
        save_config_file(config)
        return True
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        return False

