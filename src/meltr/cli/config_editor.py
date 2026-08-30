"""Interactive configuration editor assistant."""

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table

from meltr.cli.menu import paginate_choose
from meltr.core.config import (
    Config,
    GeneratorConfig,
    INTERNAL_LOGS_TEMPLATE_SENTINEL,
    OutputDefinition,
    OutputRotationConfig,
    ScheduleConfig,
    load_config,
)
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME
from meltr.core.config import (
    save_config as save_config_file,
)
from meltr.core.paths import get_logforge_home
from meltr.templates.loader import TemplateLoader

# Sentinel: user chose "back" in paginated list (not a template/vendor/product id)
_MENU_BACK = "__menu_back__"

if TYPE_CHECKING:
    from meltr.templates.loader import TemplateInfo

console = Console()


def _is_expected_local_service_down(api_url: str, error: Exception) -> bool:
    """Return True when failure matches local service-not-running case."""
    try:
        hostname = (urlparse(api_url).hostname or "").lower()
    except Exception:
        hostname = ""

    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False

    error_text = str(error).lower()
    refused_markers = (
        "connection refused",
        "[errno 111]",
        "[winerror 10061]",
        "failed to establish a new connection",
    )
    return any(marker in error_text for marker in refused_markers)


def config_editor(
    section: str | None = None,
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
            from meltr.core.config import create_default_config

            home = get_logforge_home()
            config = create_default_config(home)
            console.print("[green]Starting with default configuration[/green]\n")
    except FileNotFoundError:
        console.print("[yellow]No existing config found. Starting fresh.[/yellow]\n")
        from meltr.core.config import create_default_config

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
            console.print(
                "[yellow]Available sections: outputs, generators, api, engine, logging[/yellow]"
            )
            return

        if Confirm.ask("\nSave changes?", default=True):
            _save_config(config)
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
    console.print("\n[bold]MELTr Configuration Editor[/bold]\n")

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

    return Prompt.ask(
        "\nSelect option", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1"
    )


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
                    if output.include_metadata:
                        details.append("metadata: enabled")
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


def _create_output_interactive() -> OutputDefinition | None:
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
    default_path = "${MELTR_HOME}/outputs/{generator}-{date}.log"

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


def _prompt_plaintext_token(prompt_text: str) -> str:
    """Prompt for token value and enforce minimal safety/validity checks."""
    while True:
        token = Prompt.ask(prompt_text).strip()
        if not token:
            console.print("[red]Token cannot be empty.[/red]")
            continue
        if "${" in token:
            console.print("[red]Token cannot contain '${'.[/red]")
            continue
        return token


def _prompt_header_name(default: str = "X-API-Key") -> str:
    """Prompt for a header name and require a non-empty value."""
    while True:
        header_name = Prompt.ask("API key header name", default=default).strip()
        if not header_name:
            console.print("[red]Header name cannot be empty.[/red]")
            continue
        return header_name


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
            token_value = _prompt_plaintext_token("Bearer token")
            headers["Authorization"] = f"Bearer {token_value}"
        elif auth_type == "Splunk HEC":
            token_value = _prompt_plaintext_token("HEC token")
            headers["Authorization"] = f"Splunk {token_value}"
        else:  # API Key
            header_name = _prompt_header_name()
            token_value = _prompt_plaintext_token("API key token")
            headers[header_name] = token_value

    # Add Content-Type
    headers["Content-Type"] = "application/json"

    # Batching
    batch_size = IntPrompt.ask("Batch size (events per batch)", default=100)
    batch_interval = IntPrompt.ask("Batch interval (seconds)", default=5)
    timeout = IntPrompt.ask("Request timeout (seconds)", default=30)

    # Metadata wrapping
    include_metadata = Confirm.ask(
        "Include meltr_metadata wrapper? (wraps events with routing metadata)",
        default=False,
    )

    return OutputDefinition(
        name=name,
        type="http",
        url=url,
        method=method,
        headers=headers,
        batch_size=batch_size,
        batch_interval=batch_interval,
        timeout=timeout,
        include_metadata=include_metadata,
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
        choices=[
            "kern",
            "user",
            "mail",
            "daemon",
            "auth",
            "syslog",
            "lpr",
            "news",
            "uucp",
            "cron",
            "authpriv",
            "ftp",
            "local0",
            "local1",
            "local2",
            "local3",
            "local4",
            "local5",
            "local6",
            "local7",
        ],
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


def _build_rotation_from_prompts(
    existing: OutputRotationConfig | None = None,
) -> OutputRotationConfig | None:
    """Interactive rotation config; defaults from *existing* when set."""
    rotation_type = Prompt.ask(
        "Rotation type",
        choices=["size", "time"],
        default=(existing.type if existing else "size"),
    )
    max_size = None
    max_age = None
    if rotation_type == "size":
        max_size = Prompt.ask(
            "Max file size (e.g., 100MB, 1GB)",
            default=(str(existing.max_size) if existing and existing.max_size else "100MB"),
        )
    else:
        max_age = Prompt.ask(
            "Max age (e.g., 7d, 24h, 1w)",
            default=(existing.max_age if existing and existing.max_age else "7d"),
        )
    max_files = IntPrompt.ask(
        "Maximum rotated files to keep",
        default=(existing.max_files if existing and existing.max_files is not None else 10),
    )
    compress = Confirm.ask(
        "Compress rotated files?",
        default=(existing.compress if existing else True),
    )
    return OutputRotationConfig(
        type=rotation_type,
        max_size=max_size,
        max_age=max_age,
        max_files=max_files,
        compress=compress,
    )


def _edit_file_output_definition(output: OutputDefinition) -> OutputDefinition:
    path = Prompt.ask(
        "File path (supports variables: {generator}, {date}, …)",
        default=output.path or "",
    )
    rotation = output.rotation
    if Confirm.ask("Edit rotation settings?", default=False):
        rotation = _build_rotation_from_prompts(output.rotation)
    new_path = path.strip() if path else output.path
    return output.model_copy(update={"path": new_path, "rotation": rotation})


def _edit_console_output_definition(output: OutputDefinition) -> OutputDefinition:
    stream = Prompt.ask(
        "Stream",
        choices=["stdout", "stderr"],
        default=output.stream or "stdout",
    )
    format_type = Prompt.ask(
        "Format",
        choices=["json", "text"],
        default=output.format or "json",
    )
    return output.model_copy(update={"stream": stream, "format": format_type})


def _edit_http_output_definition(output: OutputDefinition) -> OutputDefinition:
    url = Prompt.ask("HTTP URL", default=output.url or "https://api.example.com/v1/events")
    method = Prompt.ask(
        "HTTP method",
        choices=["POST", "PUT", "PATCH"],
        default=output.method or "POST",
    )
    batch_size = IntPrompt.ask(
        "Batch size (events per batch, batching mode)",
        default=output.batch_size or 100,
    )
    batch_interval = IntPrompt.ask(
        "Batch interval (seconds)",
        default=output.batch_interval or 5,
    )
    timeout = IntPrompt.ask("Request timeout (seconds)", default=output.timeout or 30)
    streaming = Confirm.ask(
        "Streaming mode (send each event as generated)?",
        default=output.streaming if output.streaming is not None else True,
    )
    include_metadata = Confirm.ask(
        "Include meltr_metadata wrapper?",
        default=output.include_metadata,
    )
    policy = Prompt.ask(
        "Buffer overflow policy when retry queue is full",
        choices=["drop_newest", "drop_oldest"],
        default=output.buffer_overflow_policy,
    )
    updates = {
        "url": url,
        "method": method,
        "batch_size": batch_size,
        "batch_interval": batch_interval,
        "timeout": timeout,
        "streaming": streaming,
        "include_metadata": include_metadata,
        "buffer_overflow_policy": policy,
    }
    if Confirm.ask("Rebuild authentication headers from presets?", default=False):
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if Confirm.ask("Add authentication header?", default=False):
            auth_type = Prompt.ask(
                "Authentication type",
                choices=["Bearer", "Splunk HEC", "API Key"],
                default="Bearer",
            )
            if auth_type == "Bearer":
                token_value = _prompt_plaintext_token("Bearer token")
                headers["Authorization"] = f"Bearer {token_value}"
            elif auth_type == "Splunk HEC":
                token_value = _prompt_plaintext_token("HEC token")
                headers["Authorization"] = f"Splunk {token_value}"
            else:
                header_name = _prompt_header_name()
                token_value = _prompt_plaintext_token("API key token")
                headers[header_name] = token_value
        updates["headers"] = headers
    return output.model_copy(update=updates)


def _edit_tcp_output_definition(output: OutputDefinition) -> OutputDefinition:
    host = Prompt.ask("Host", default=output.host or "localhost")
    port = IntPrompt.ask("Port", default=output.port or 514)
    delimiter = Prompt.ask("Delimiter", default=output.delimiter or "\\n")
    keepalive = Confirm.ask(
        "Enable TCP keepalive?",
        default=output.keepalive if output.keepalive is not None else True,
    )
    return output.model_copy(
        update={
            "host": host,
            "port": port,
            "delimiter": delimiter,
            "keepalive": keepalive,
        }
    )


def _edit_syslog_output_definition(output: OutputDefinition) -> OutputDefinition:
    host = Prompt.ask("Syslog server host", default=output.host or "localhost")
    port = IntPrompt.ask("Port", default=output.port or 514)
    protocol = Prompt.ask(
        "Protocol",
        choices=["tcp", "udp"],
        default=output.protocol or "udp",
    )
    facility = Prompt.ask(
        "Facility",
        choices=[
            "kern",
            "user",
            "mail",
            "daemon",
            "auth",
            "syslog",
            "lpr",
            "news",
            "uucp",
            "cron",
            "authpriv",
            "ftp",
            "local0",
            "local1",
            "local2",
            "local3",
            "local4",
            "local5",
            "local6",
            "local7",
        ],
        default=output.facility or "user",
    )
    severity = Prompt.ask(
        "Severity",
        choices=[
            "emerg",
            "alert",
            "crit",
            "err",
            "warning",
            "notice",
            "info",
            "debug",
        ],
        default=output.severity or "info",
    )
    return output.model_copy(
        update={
            "host": host,
            "port": port,
            "protocol": protocol,
            "facility": facility,
            "severity": severity,
        }
    )


def _prompt_edit_output_definition(output: OutputDefinition) -> OutputDefinition:
    editors = {
        "file": _edit_file_output_definition,
        "console": _edit_console_output_definition,
        "http": _edit_http_output_definition,
        "tcp": _edit_tcp_output_definition,
        "syslog": _edit_syslog_output_definition,
    }
    fn = editors.get(output.type)
    if fn is None:
        console.print(f"[red]No editor for output type '{output.type}'[/red]")
        return output
    return fn(output)


def _edit_output_interactive(config: Config) -> Config:
    """Edit an existing output."""
    if not config.outputs.definitions:
        console.print("[yellow]No outputs to edit[/yellow]")
        return config

    console.print("\n[bold]Select Output to Edit[/bold]\n")
    for i, out in enumerate(config.outputs.definitions, 1):
        console.print(f"  [{i}] {out.name} ({out.type})")

    choice = IntPrompt.ask("\nSelect output number", default=1)
    if choice < 1 or choice > len(config.outputs.definitions):
        console.print("[red]Invalid selection[/red]")
        return config

    output = config.outputs.definitions[choice - 1]
    console.print(f"\n[bold]Editing: {output.name}[/bold]\n")

    updated = _prompt_edit_output_definition(output)
    config.outputs.definitions[choice - 1] = updated
    console.print("[green]✓ Output updated[/green]")
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

    referencing = [gen.name for gen in config.generators if output.name in gen.outputs]
    if referencing:
        console.print(
            f"\n[yellow]Warning: these generators reference output '{output.name}':[/yellow]"
        )
        for gen_name in referencing:
            console.print(f"  • {gen_name}")
        if not Confirm.ask("\nRemove output anyway?", default=False):
            return config

    if Confirm.ask(f"\n[yellow]Remove output '{output.name}'?", default=False):
        config.outputs.definitions.pop(choice - 1)
        console.print(f"[green]✓ Removed output: {output.name}[/green]")

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

    from meltr.core.config import RetryConfig

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


def _is_reserved_generator_name(name: str) -> bool:
    """Return True for generators that cannot be removed or scheduled."""
    return name == INTERNAL_LOGS_GENERATOR_NAME


def _format_generator_template(gen: GeneratorConfig) -> str:
    """Human-readable template column for generator listings."""
    if _is_reserved_generator_name(gen.name):
        return "(application logs)"
    if gen.template == INTERNAL_LOGS_TEMPLATE_SENTINEL:
        return "(application logs)"
    return gen.template


def _format_generator_schedule(gen: GeneratorConfig) -> str:
    """Human-readable schedule column for generator listings."""
    if _is_reserved_generator_name(gen.name):
        return "n/a"
    if gen.schedule is None or gen.schedule.mode == "continuous":
        return "continuous"
    return gen.schedule.mode


def _remove_generator(config: Config, name: str) -> tuple[Config, bool]:
    """Remove a generator by name. Reserved generators cannot be removed."""
    if _is_reserved_generator_name(name):
        return config, False
    before = len(config.generators)
    config.generators = [g for g in config.generators if g.name != name]
    return config, len(config.generators) < before


def _prompt_output_selection(
    config: Config,
    *,
    current_outputs: list[str] | None = None,
    default_indices: str | None = None,
) -> list[str] | None:
    """Prompt for one or more outputs by number. Returns output names or None."""
    if not config.outputs.definitions:
        console.print("[yellow]No outputs configured. Please add outputs first.[/yellow]")
        return None

    console.print("\n[bold]Select Outputs[/bold]\n")
    for i, output in enumerate(config.outputs.definitions, 1):
        console.print(f"  [{i}] {output.name} ({output.type})")

    if default_indices is None and current_outputs:
        default_indices = ",".join(
            str(i + 1)
            for i, o in enumerate(config.outputs.definitions)
            if o.name in current_outputs
        )

    output_choices = Prompt.ask(
        "\nSelect output numbers (comma-separated, e.g., 1,2)",
        default=default_indices or "1",
    )

    try:
        indices = [int(x.strip()) - 1 for x in output_choices.split(",")]
        selected_outputs = [
            config.outputs.definitions[i].name
            for i in indices
            if 0 <= i < len(config.outputs.definitions)
        ]
    except (ValueError, IndexError):
        console.print("[red]Invalid output selection[/red]")
        return None

    if not selected_outputs:
        console.print("[red]No valid outputs selected[/red]")
        return None

    return selected_outputs


def _prompt_schedule_config(existing: ScheduleConfig | None) -> ScheduleConfig | None:
    """Prompt for optional schedule gate configuration."""
    if not Confirm.ask(
        "Configure a schedule gate?",
        default=existing is not None and existing.mode != "continuous",
    ):
        return None

    mode = Prompt.ask(
        "Schedule mode",
        choices=["continuous", "window", "burst"],
        default=(existing.mode if existing else "continuous"),
    )

    if mode == "continuous":
        return ScheduleConfig(mode="continuous")

    if mode == "window":
        default_days = ",".join(existing.days) if existing and existing.days else "mon,tue,wed,thu,fri"
        days_input = Prompt.ask("Days (comma-separated, e.g. mon,tue)", default=default_days)
        days = [d.strip() for d in days_input.split(",") if d.strip()] or None
        time_range = Prompt.ask(
            "Time range (e.g. 09:00-17:00)",
            default=(existing.time if existing and existing.time else "09:00-17:00"),
        )
        tz_input = Prompt.ask(
            "Timezone (optional)",
            default=(existing.timezone if existing and existing.timezone else ""),
        )
        return ScheduleConfig(
            mode="window",
            days=days,
            time=time_range,
            timezone=tz_input.strip() or None,
        )

    count_default = str(existing.count) if existing and existing.count is not None else "100"
    count_str = Prompt.ask("Event count limit", default=count_default)
    duration = Prompt.ask(
        "Duration limit (e.g. 5m, 1h)",
        default=(existing.duration if existing and existing.duration else "5m"),
    )
    tz_input = Prompt.ask(
        "Timezone (optional)",
        default=(existing.timezone if existing and existing.timezone else ""),
    )
    try:
        count = int(count_str)
    except ValueError:
        count = 100
    return ScheduleConfig(
        mode="burst",
        count=count,
        duration=duration,
        timezone=tz_input.strip() or None,
    )


def _set_generator_schedule_interactive(
    config: Config,
    name: str | None = None,
) -> Config:
    """Set or clear schedule on a non-reserved generator."""
    if name is None:
        selectable = [g for g in config.generators if not _is_reserved_generator_name(g.name)]
        if not selectable:
            console.print("[yellow]No generators available for schedule configuration[/yellow]")
            return config

        console.print("\n[bold]Select Generator for Schedule[/bold]\n")
        for i, gen in enumerate(selectable, 1):
            schedule_label = _format_generator_schedule(gen)
            console.print(f"  [{i}] {gen.name} ({schedule_label})")

        choice = IntPrompt.ask("\nSelect generator number", default=1)
        if choice < 1 or choice > len(selectable):
            console.print("[red]Invalid selection[/red]")
            return config
        name = selectable[choice - 1].name

    if _is_reserved_generator_name(name):
        console.print(
            f"[red]Cannot set schedule on reserved generator '{INTERNAL_LOGS_GENERATOR_NAME}'[/red]"
        )
        return config

    gen = next((g for g in config.generators if g.name == name), None)
    if gen is None:
        console.print(f"[red]Generator '{name}' not found[/red]")
        return config

    gen.schedule = _prompt_schedule_config(gen.schedule)
    console.print(f"[green]✓ Schedule updated for {gen.name}[/green]")
    return config


def _edit_generators_section(config: Config) -> Config:
    """Edit generators section interactively."""
    console.print("\n[bold]Generator Management[/bold]\n")

    while True:
        if config.generators:
            table = Table(title="Current Generators")
            table.add_column("Name", style="cyan")
            table.add_column("Template", style="green")
            table.add_column("Enabled", style="yellow")
            table.add_column("Schedule", style="magenta")
            table.add_column("Outputs", style="blue")

            for gen in config.generators:
                outputs_str = ", ".join(gen.outputs) if gen.outputs else "none"
                table.add_row(
                    gen.name,
                    _format_generator_template(gen),
                    "✓" if gen.enabled else "✗",
                    _format_generator_schedule(gen),
                    outputs_str,
                )

            console.print(table)
        else:
            console.print("[yellow]No generators configured[/yellow]\n")

        console.print("\n[cyan]Options:[/cyan]")
        console.print("  [1] Add generator")
        console.print("  [2] Edit generator")
        console.print("  [3] Remove generator")
        console.print("  [4] Set schedule…")
        console.print("  [5] Back to main menu")

        choice = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4", "5"], default="5")

        if choice == "1":
            new_gen = _create_generator_interactive(config)
            if new_gen:
                config.generators.append(new_gen)
                console.print(f"[green]✓ Added generator: {new_gen.name}[/green]")
        elif choice == "2":
            config = _edit_generator_interactive(config)
        elif choice == "3":
            config = _remove_generator_interactive(config)
        elif choice == "4":
            config = _set_generator_schedule_interactive(config)
        elif choice == "5":
            break

    return config


def _generate_generator_name(
    template_id: str,
    template_info: "TemplateInfo",
    existing_names: set[str],
) -> str:
    """Generate a suggested generator name from template metadata.

    Args:
        template_id: Template ID
        template_info: TemplateInfo object
        existing_names: Set of existing generator names

    Returns:
        Suggested generator name (unique if possible)
    """
    # Extract template name from metadata
    template_name = template_info.name

    # Normalize: lowercase, replace spaces/special chars with underscores
    import re

    normalized = re.sub(r"[^a-z0-9_]+", "_", template_name.lower())
    normalized = re.sub(r"_+", "_", normalized)  # Replace multiple underscores
    normalized = normalized.strip("_")  # Remove leading/trailing underscores

    if not normalized:
        # Fallback: use template ID parts
        parts = template_id.split("/")
        if len(parts) >= 3:
            normalized = parts[-2].replace("-", "_") + "_" + parts[-1].replace("-", "_")
        else:
            normalized = template_id.replace("/", "_").replace("-", "_")

    # Ensure uniqueness
    base_name = normalized
    counter = 1
    name = base_name
    while name in existing_names:
        name = f"{base_name}_{counter}"
        counter += 1

    return name


def _create_generator_interactive(config: Config) -> GeneratorConfig | None:
    """Interactively create a new generator."""
    console.print("\n[bold]Create New Generator[/bold]\n")

    # Template selection (hierarchical)
    template = _select_template_interactive(config)
    if not template:
        console.print("[yellow]No template selected, cancelling[/yellow]")
        return None

    # Get template info for auto-naming
    from meltr.templates.loader import TemplateLoader

    loader = TemplateLoader(config)
    template_info = loader.resolve_template(template)

    if not template_info:
        console.print(f"[yellow]Warning: Could not load template info for {template}[/yellow]")
        suggested_name = template.split("/")[-1].replace("-", "_")
    else:
        # Generate suggested name from template metadata
        existing_names = {g.name for g in config.generators}
        suggested_name = _generate_generator_name(template, template_info, existing_names)

    # Generator name (with editable default)
    name = Prompt.ask("Generator name", default=suggested_name)

    # Check if name already exists
    if any(g.name == name for g in config.generators):
        console.print(f"[red]Generator '{name}' already exists[/red]")
        if not Confirm.ask("Use a different name?", default=True):
            return None
        name = Prompt.ask("Generator name")
        # Validate uniqueness again
        while any(g.name == name for g in config.generators):
            console.print(f"[red]Generator '{name}' already exists[/red]")
            name = Prompt.ask("Generator name")

    # Output selection
    selected_outputs = _prompt_output_selection(config)
    if not selected_outputs:
        return None

    enabled = Confirm.ask("\nEnable generator?", default=True)

    return GeneratorConfig(
        name=name,
        template=template,
        enabled=enabled,
        outputs=selected_outputs,
        schedule=None,
    )


def _get_existing_templates(config: Config) -> set[str]:
    """Get set of template IDs already configured as generators."""
    return {g.template for g in config.generators}


def _get_template_hierarchy(
    config: Config,
) -> dict[str, dict[str, list[tuple[str, "TemplateInfo"]]]]:
    """Build vendor->product->templates hierarchy structure.

    Returns:
        Dictionary structure: {vendor: {product: [(template_id, template_info), ...]}}
    """
    from meltr.templates.loader import TemplateLoader

    loader = TemplateLoader(config)
    templates = loader.discover_templates()

    hierarchy: dict[str, dict[str, list[tuple[str, TemplateInfo]]]] = {}

    for template_id, template_info in templates.items():
        vendor = template_info.vendor
        product = template_info.product

        if vendor not in hierarchy:
            hierarchy[vendor] = {}
        if product not in hierarchy[vendor]:
            hierarchy[vendor][product] = []

        hierarchy[vendor][product].append((template_id, template_info))

    # Sort templates within each product
    for vendor in hierarchy:
        for product in hierarchy[vendor]:
            hierarchy[vendor][product].sort(key=lambda x: x[0])

    return hierarchy


def _select_template_from_product(
    config: Config,
    vendor: str,
    product: str,
) -> str | None:
    """Select a template from a specific vendor/product."""
    hierarchy = _get_template_hierarchy(config)
    existing_templates = _get_existing_templates(config)

    if vendor not in hierarchy or product not in hierarchy[vendor]:
        console.print(f"[red]No templates found for {vendor}/{product}[/red]")
        return None

    templates = hierarchy[vendor][product]
    if not templates:
        console.print(f"[yellow]No available templates for {vendor}/{product}[/yellow]")
        return None

    # Build display items
    items = []
    for template_id, _template_info in templates:
        # Format: data_source/template_name
        parts = template_id.split("/")
        if len(parts) >= 4:
            display_name = f"{parts[2]}/{parts[3]}"
        else:
            display_name = template_id

        marker = " ✓" if template_id in existing_templates else ""
        items.append((f"{display_name}{marker}", template_id))

    total_count = len(templates)
    existing_count = sum(1 for tid, _ in templates if tid in existing_templates)

    title = f"Templates: {vendor}/{product} ({total_count} available"
    if existing_count > 0:
        title += f", {existing_count} already configured"
    title += ")"

    selection = paginate_choose(items, console=console, page_size=20, title=title)
    if selection is None:
        return None
    if selection < 0:
        return _MENU_BACK

    selected_template_id = items[selection][1]
    console.print(f"[green]Selected: {selected_template_id}[/green]")
    return selected_template_id


def _select_product(config: Config, vendor: str) -> str | None:
    """Select a product for a vendor."""
    hierarchy = _get_template_hierarchy(config)
    existing_templates = _get_existing_templates(config)

    if vendor not in hierarchy:
        console.print(f"[red]Vendor '{vendor}' not found[/red]")
        return None

    products = sorted(hierarchy[vendor].keys())

    # Build display items with counts
    items = []
    for product in products:
        templates = hierarchy[vendor][product]
        total_count = len(templates)
        existing_count = sum(1 for tid, _ in templates if tid in existing_templates)
        if existing_count > 0:
            items.append(
                (f"{product} ({total_count} templates, {existing_count} configured)", product)
            )
        else:
            items.append((f"{product} ({total_count} templates)", product))

    if not items:
        console.print(f"[yellow]No products with available templates for {vendor}[/yellow]")
        return None

    title = f"Products: {vendor}"
    selection = paginate_choose(items, console=console, page_size=20, title=title)
    if selection is None:
        return None
    if selection < 0:
        return _MENU_BACK

    selected_product = items[selection][1]
    return selected_product


def _select_vendor(config: Config) -> str | None:
    """Select a vendor."""
    hierarchy = _get_template_hierarchy(config)
    existing_templates = _get_existing_templates(config)

    vendors = sorted(hierarchy.keys())

    # Build display items with counts
    items = []
    for vendor in vendors:
        products = hierarchy[vendor]
        total_templates = sum(len(templates) for templates in products.values())
        total_products = len(products)
        existing_count = sum(
            1
            for templates in products.values()
            for tid, _ in templates
            if tid in existing_templates
        )
        if existing_count > 0:
            items.append(
                (
                    f"{vendor} ({total_products} products, {total_templates} templates, {existing_count} configured)",
                    vendor,
                )
            )
        else:
            items.append(
                (f"{vendor} ({total_products} products, {total_templates} templates)", vendor)
            )

    if not items:
        console.print("[yellow]No vendors with available templates[/yellow]")
        return None

    title = "Select Vendor"
    selection = paginate_choose(items, console=console, page_size=20, title=title)
    if selection is None or selection < 0:
        return None

    selected_vendor = items[selection][1]
    return selected_vendor


def _select_template_hierarchical(config: Config) -> str | None:
    """Hierarchical template selection: vendor -> product -> template."""
    while True:
        vendor = _select_vendor(config)
        if not vendor:
            return None

        while True:
            product = _select_product(config, vendor)
            if product is None:
                return None
            if product == _MENU_BACK:
                break

            while True:
                template = _select_template_from_product(config, vendor, product)
                if template is None:
                    return None
                if template == _MENU_BACK:
                    break
                return template


def _select_template_interactive(config: Config) -> str | None:
    """Interactively select a template using hierarchical navigation."""
    try:
        loader = TemplateLoader(config)
        templates = loader.discover_templates()

        if not templates:
            console.print("[yellow]No templates found. Install templates first.[/yellow]")
            return None

        return _select_template_hierarchical(config)

    except Exception as e:
        console.print(f"[red]Error loading templates: {e}[/red]")
        # Fallback: manual entry
        template = Prompt.ask(
            "\nEnter template ID manually (e.g., paloalto/wildfire/threats/wildfire_threat_detected)"
        )
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

    if _is_reserved_generator_name(gen.name):
        gen.enabled = Confirm.ask("Enable generator?", default=gen.enabled)
        console.print(
            "[dim]internal-logs forwards application logs to outputs (no template)[/dim]"
        )
        if Confirm.ask("Edit outputs?", default=not gen.outputs):
            selected = _prompt_output_selection(config, current_outputs=gen.outputs)
            if selected:
                gen.outputs = selected
        console.print("[green]✓ Generator updated[/green]")
        return config

    gen.enabled = Confirm.ask("Enable generator?", default=gen.enabled)

    console.print("\n[dim]Frequency is read from template metadata (.meta.yaml)[/dim]")
    console.print("[dim]To customize, copy template to custom/ directory and edit .meta.yaml[/dim]")

    if Confirm.ask("\nEdit timezone override?", default=False):
        current_tz = gen.timezone or "(using organization timezone)"
        console.print(f"\n[bold]Current timezone:[/bold] {current_tz}")
        console.print("[dim]Leave empty to use organization timezone from entities.yaml[/dim]")
        timezone_input = Prompt.ask("Timezone override (optional)", default=gen.timezone or "")
        gen.timezone = timezone_input.strip() if timezone_input.strip() else None

    if Confirm.ask("Edit outputs?", default=False):
        selected = _prompt_output_selection(config, current_outputs=gen.outputs)
        if selected:
            gen.outputs = selected

            selected_defs = [
                o for o in config.outputs.definitions if o.name in gen.outputs
            ]
            http_outputs = [output for output in selected_defs if output.type == "http"]
            if http_outputs:
                console.print("\n[bold]HTTP Output Metadata Configuration[/bold]")
                for output in http_outputs:
                    current_setting = "enabled" if output.include_metadata else "disabled"
                    console.print(f"\n[cyan]{output.name}[/cyan] (current: {current_setting})")
                    output.include_metadata = Confirm.ask(
                        f"  Include meltr_metadata wrapper for {output.name}?",
                        default=output.include_metadata,
                    )

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

    if _is_reserved_generator_name(gen.name):
        console.print(
            f"[red]Cannot remove reserved generator '{INTERNAL_LOGS_GENERATOR_NAME}'[/red]"
        )
        return config

    if Confirm.ask(f"\n[yellow]Remove generator '{gen.name}'?", default=False):
        config, removed = _remove_generator(config, gen.name)
        if removed:
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

            from meltr.core.config import RotationConfig

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

    config_dict = config.model_dump(mode="json", exclude_none=True)
    output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

    from rich.syntax import Syntax

    syntax = Syntax(output, "yaml", theme="monokai")
    console.print(syntax)


def _save_config(config: Config) -> bool:
    """Save configuration with confirmation and automatic validation/application."""
    _preview_config(config)

    if not Confirm.ask("\n[yellow]Save this configuration?", default=True):
        return False

    try:
        # Validate config before saving
        try:
            # Try to create a Config object from the dict to validate
            config_dict = config.model_dump(mode="json")
            # Validate by attempting to create a new Config object
            Config(**config_dict)
            console.print("[green]✓ Configuration validated[/green]")
        except Exception as e:
            console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
            if not Confirm.ask("[yellow]Save anyway? (not recommended)[/yellow]", default=False):
                return False

        # Save to file
        save_config_file(config)
        console.print("[green]✓ Configuration saved[/green]")

        # Try to apply changes automatically (if service is running)
        try:
            import requests

            from meltr.cli.api_client import get_api_client

            client = get_api_client()

            # Check if service is running
            try:
                health_response = client.get("/api/health", timeout=5.0)
                if health_response.status_code == 200:
                    # Service is running, apply changes
                    console.print("[cyan]Applying configuration changes...[/cyan]")
                    reload_response = client.post("/api/config/reload", timeout=30.0)
                    reload_response.raise_for_status()
                    reload_data = reload_response.json()

                    results = reload_data.get("results", {})
                    added = results.get("added", [])
                    removed = results.get("removed", [])
                    updated = results.get("updated", [])
                    errors = results.get("errors", [])

                    if added:
                        console.print(
                            f"[green]✓ Started {len(added)} new generator(s): {', '.join(added)}[/green]"
                        )
                    if removed:
                        console.print(
                            f"[yellow]✓ Stopped {len(removed)} removed generator(s): {', '.join(removed)}[/yellow]"
                        )
                    if updated:
                        console.print(
                            f"[cyan]✓ Updated {len(updated)} generator(s): {', '.join(updated)}[/cyan]"
                        )
                    if errors:
                        console.print("[red]⚠ Errors during reload:[/red]")
                        for error in errors:
                            console.print(f"  [red]- {error}[/red]")

                    if not (added or removed or updated or errors):
                        console.print(
                            "[green]✓ Configuration applied (no generator changes)[/green]"
                        )
                    else:
                        console.print(
                            "[green]✓ Configuration changes applied successfully![/green]"
                        )
                else:
                    console.print(
                        f"[yellow]⚠ Service returned status {health_response.status_code}. Restart service to apply changes.[/yellow]"
                    )
            except requests.exceptions.ConnectionError as e:
                if _is_expected_local_service_down(client.api_url, e):
                    console.print("[dim]ℹ Service is not running; skipping live reload.[/dim]")
                    console.print(
                        "[dim]  Saved config will be loaded automatically on next start.[/dim]"
                    )
                else:
                    console.print(
                        f"[yellow]⚠ Could not connect to service at {client.api_url}[/yellow]"
                    )
                    console.print(f"[yellow]  Error: {str(e)}[/yellow]")
                    console.print(
                        "[yellow]  Use 'meltr config reload' after starting the service.[/yellow]"
                    )
            except requests.exceptions.Timeout:
                console.print(
                    "[yellow]⚠ Service health check timed out (service may be slow or unresponsive)[/yellow]"
                )
                console.print(
                    "[yellow]  Use 'meltr config reload' to apply changes manually.[/yellow]"
                )
            except Exception as e:
                # Show actual error for debugging
                console.print(
                    f"[yellow]⚠ Could not apply changes automatically: {type(e).__name__}: {str(e)}[/yellow]"
                )
                console.print(
                    "[yellow]  Use 'meltr config reload' to apply changes manually.[/yellow]"
                )
        except Exception as e:
            # API client not available or service not running
            console.print(
                f"[yellow]⚠ Could not apply changes automatically: {type(e).__name__}: {str(e)}[/yellow]"
            )
            console.print(
                "[yellow]  Use 'meltr config reload' to apply changes manually.[/yellow]"
            )

        return True
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        return False
