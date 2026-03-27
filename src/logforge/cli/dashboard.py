"""Performance dashboard CLI command."""

import time
from typing import Any, Optional

import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from logforge.cli.api_client import get_api_client

app = typer.Typer(name="dashboard", help="Performance dashboard", invoke_without_command=True)
console = Console()


@app.callback(invoke_without_command=True)
def dashboard_callback(
    ctx: typer.Context,
    refresh_rate: float = typer.Option(1.0, "--refresh", "-r", help="Refresh rate in seconds"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Display real-time performance dashboard.

    Shows CPU, memory, thread count, and generator statistics in a live-updating dashboard.
    Press Ctrl+C to exit.
    """
    if ctx.invoked_subcommand is None:
        dashboard_show(refresh_rate=refresh_rate, api_url=api_url, api_key=api_key)


def _format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def _get_cpu_color(cpu_percent: float) -> str:
    """Get color for CPU usage."""
    if cpu_percent >= 80:
        return "red"
    elif cpu_percent >= 50:
        return "yellow"
    else:
        return "green"


def _get_memory_color(memory_mb: int, threshold_mb: int = 1024) -> str:
    """Get color for memory usage."""
    if memory_mb >= threshold_mb * 2:
        return "red"
    elif memory_mb >= threshold_mb:
        return "yellow"
    else:
        return "green"


def fetch_status_snapshot(client) -> dict[str, Any]:
    """Fetch a status snapshot from the running service."""
    response = client.get("/api/status")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"unexpected /api/status payload type: {type(data).__name__}")
    return data


def render_status_snapshot(snapshot: dict[str, Any], refresh_count: int = 0) -> Layout:
    """Render a dashboard layout from a status snapshot."""
    data = snapshot

    # System metrics
    system = data.get("system", {})
    cpu_percent = system.get("cpu_percent", 0.0)
    memory_mb = system.get("memory_mb", 0)
    threads = system.get("threads", 0)
    uptime = data.get("uptime", 0)

    # Create layout
    layout = Layout()

    # Top section: System metrics
    system_table = Table.grid(padding=(0, 2))
    system_table.add_column(style="cyan", justify="right", width=12)
    system_table.add_column(style="white", width=30)

    # CPU with visual indicator
    cpu_color = _get_cpu_color(cpu_percent)
    cpu_bar = "█" * int(cpu_percent / 2) + "░" * (50 - int(cpu_percent / 2))
    system_table.add_row(
        "CPU:",
        f"[{cpu_color}]{cpu_percent:5.1f}%[/{cpu_color}] [{cpu_color}]{cpu_bar}[/{cpu_color}]"
    )

    # Memory
    memory_gb = memory_mb / 1024
    memory_color = _get_memory_color(memory_mb)
    system_table.add_row(
        "Memory:",
        f"[{memory_color}]{memory_mb:6d} MB[/{memory_color}] ({memory_gb:.2f} GB)"
    )

    # Threads
    system_table.add_row("Threads:", f"[green]{threads}[/green]")

    # Uptime
    uptime_str = _format_uptime(uptime)
    system_table.add_row("Uptime:", f"[cyan]{uptime_str}[/cyan]")

    # Refresh counter
    system_table.add_row("Refresh:", f"[dim]#{refresh_count}[/dim]")

    system_panel = Panel(
        system_table,
        title="[bold blue]System Metrics[/bold blue]",
        border_style="blue"
    )

    # Middle section: Generators
    generators_table = Table(show_header=True, header_style="bold magenta")
    generators_table.add_column("Name", style="cyan", width=30)
    generators_table.add_column("State", style="green", width=12, justify="center")
    generators_table.add_column("Events", style="magenta", justify="right", width=12)
    generators_table.add_column("Errors", style="red", justify="right", width=10)
    generators_table.add_column("Rate", style="yellow", justify="right", width=12)
    generators_table.add_column("Uptime", style="blue", width=12)

    total_events = 0
    total_errors = 0
    running_count = 0

    generators = data.get("generators", [])

    for gen in generators:
        name = gen.get("name", "unknown")
        state = gen.get("state", "UNKNOWN")
        events = gen.get("events_generated", 0)
        errors = gen.get("errors", 0)
        uptime_gen = gen.get("uptime", 0)

        # Calculate rate
        rate = events / uptime_gen if uptime_gen > 0 else 0
        rate_str = f"{rate:.2f}/s" if rate > 0 else "0/s"

        state_color = {
            "RUNNING": "green",
            "STOPPED": "dim white",
            "ERROR": "red",
            "DEGRADED": "yellow",
            "STARTING": "blue",
            "STOPPING": "yellow",
        }.get(state, "white")

        generators_table.add_row(
            escape(str(name)),
            f"[{state_color}]{escape(str(state))}[/{state_color}]",
            f"{events:,}",
            f"[red]{errors:,}[/red]" if errors > 0 else f"{errors:,}",
            rate_str,
            _format_uptime(uptime_gen),
        )

        total_events += events
        total_errors += errors
        if state == "RUNNING":
            running_count += 1

    # Summary row
    generators_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{running_count}/{len(generators)}[/bold]",
        f"[bold]{total_events:,}[/bold]",
        f"[bold red]{total_errors:,}[/bold]" if total_errors > 0 else f"[bold green]{total_errors:,}[/bold]",
        "",
        "",
        style="bold"
    )

    generators_panel = Panel(
        generators_table,
        title=f"[bold green]Generators[/bold green] ({len(generators)} total)",
        border_style="green"
    )

    # Bottom section: Summary stats
    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style="cyan", justify="right", width=20)
    summary_table.add_column(style="white", width=30)

    summary_table.add_row("Total Events:", f"[bold cyan]{total_events:,}[/bold cyan]")
    error_style = "bold red" if total_errors > 0 else "bold green"
    summary_table.add_row("Total Errors:", f"[{error_style}]{total_errors:,}[/{error_style}]")
    summary_table.add_row("Running Generators:", f"[bold green]{running_count}[/bold green] / [dim]{len(generators)}[/dim]")

    # Calculate average rate
    if generators:
        uptime_gens = [g for g in generators if g.get("uptime", 0) > 0]
        if uptime_gens:
            avg_rate = sum(
                gen.get("events_generated", 0) / gen.get("uptime", 1)
                for gen in uptime_gens
            ) / len(uptime_gens)
            summary_table.add_row(
                "Avg Event Rate:",
                f"[bold yellow]{avg_rate:.2f} events/sec[/bold yellow]",
            )

    summary_panel = Panel(
        summary_table,
        title="[bold yellow]Summary[/bold yellow]",
        border_style="yellow"
    )

    # Arrange layout
    layout.split_column(
        Layout(system_panel, size=8),
        Layout(generators_panel, ratio=2),
        Layout(summary_panel, size=7),
    )

    return layout


def _safe_error_layout(title: str, message: str) -> Layout:
    panel = Panel(
        message,
        title=title,
        border_style="red",
    )
    return Layout(panel)


def safe_render_tick(client, refresh_count: int) -> Layout:
    """Fetch+render a tick, always returning a Layout (never raises)."""
    try:
        snapshot = fetch_status_snapshot(client)
        return render_status_snapshot(snapshot, refresh_count)
    except Exception as e:
        return _safe_error_layout(
            "[bold red]Error[/bold red]",
            f"[red]Dashboard error[/red]: {escape(str(e))}",
        )


@app.command("show")
def dashboard_show(
    refresh_rate: float = typer.Option(1.0, "--refresh", "-r", help="Refresh rate in seconds"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Display real-time performance dashboard.

    Shows CPU, memory, thread count, and generator statistics in a live-updating dashboard.
    Press Ctrl+C to exit.
    """
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    refresh_count = 0

    # Display live dashboard
    try:
        with Live(
            safe_render_tick(client, refresh_count),
            refresh_per_second=1.0 / refresh_rate if refresh_rate > 0 else 1.0,
            screen=True,
            redirect_stderr=False
        ) as live:
            while True:
                time.sleep(refresh_rate)
                refresh_count += 1
                live.update(safe_render_tick(client, refresh_count))
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard closed[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {escape(str(e))}[/red]")
        raise typer.Exit(code=1) from None

