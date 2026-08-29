"""Generator management CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from meltr.cli.api_client import get_api_client

app = typer.Typer(name="generators", help="Generator management")
console = Console()


@app.command("list")
def generators_list(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show additional columns (vendor, product, data_source)"
    ),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """List all generators in alphabetical order."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.get("/api/generators")
        response.raise_for_status()
        data = response.json()

        # Sort generators alphabetically by name
        generators = sorted(data["generators"], key=lambda x: x["name"].lower())

        table = Table(title="Generators")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Template", style="yellow")
        table.add_column("Enabled", style="magenta")

        # Add verbose columns if requested
        if verbose:
            table.add_column("Vendor", style="blue")
            table.add_column("Product", style="blue")
            table.add_column("Data Source", style="blue")

        for gen in generators:
            state_style = {
                "RUNNING": "green",
                "STOPPED": "dim",
                "ERROR": "red",
                "DEGRADED": "yellow",
                "STARTING": "blue",
                "STOPPING": "yellow",
            }.get(gen["state"], "white")

            row_data = [
                gen["name"],
                f"[{state_style}]{gen['state']}[/{state_style}]",
                gen["template"],
                "✓" if gen["enabled"] else "✗",
            ]

            # Add verbose columns if requested
            if verbose:
                row_data.extend(
                    [
                        gen.get("vendor", "N/A") or "N/A",
                        gen.get("product", "N/A") or "N/A",
                        gen.get("data_source", "N/A") or "N/A",
                    ]
                )

            table.add_row(*row_data)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("start")
def generators_start(
    name: str = typer.Argument(..., help="Generator name"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Start a generator."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.post(f"/api/generators/{name}/start", json={})
        response.raise_for_status()
        data = response.json()

        console.print(f"[green]✓ {data['message']}[/green]")
        console.print(f"  Generator: {name}")
        console.print(f"  State: {data['state']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("stop")
def generators_stop(
    name: str = typer.Argument(..., help="Generator name"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Stop a generator."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.post(f"/api/generators/{name}/stop", json={})
        response.raise_for_status()
        data = response.json()

        console.print(f"[green]✓ {data['message']}[/green]")
        console.print(f"  Generator: {name}")
        console.print(f"  State: {data['state']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("restart")
def generators_restart(
    name: str | None = typer.Argument(None, help="Generator name (optional if --all is used)"),
    all_generators: bool = typer.Option(False, "--all", "-a", help="Restart all generators"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Restart a generator or all generators."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        if all_generators:
            # Restart all generators
            response = client.post("/api/generators/restart-all", json={})
            response.raise_for_status()
            data = response.json()

            console.print(f"[green]✓ {data['message']}[/green]")
            console.print(f"  Restarted: {data['count']} generator(s)")

            # Show results table if available
            if "results" in data and data["results"]:
                table = Table(title="Restart Results")
                table.add_column("Generator", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("State", style="yellow")

                for result in data["results"]:
                    status_color = "green" if result.get("success") else "red"
                    status_text = (
                        "✓ Success"
                        if result.get("success")
                        else f"✗ {result.get('error', 'Failed')}"
                    )
                    table.add_row(
                        result["name"],
                        f"[{status_color}]{status_text}[/{status_color}]",
                        result.get("state", "N/A"),
                    )
                console.print(table)
        else:
            # Restart single generator
            if not name:
                console.print("[red]Error: Generator name required (or use --all)[/red]")
                raise typer.Exit(code=1)

            response = client.post(f"/api/generators/{name}/restart", json={})
            response.raise_for_status()
            data = response.json()

            console.print(f"[green]✓ {data['message']}[/green]")
            console.print(f"  Generator: {name}")
            console.print(f"  State: {data['state']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("status")
def generators_status(
    name: str | None = typer.Argument(None, help="Generator name (optional)"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
) -> None:
    """Show generator status."""
    # Handle case where timeout might be a Typer OptionInfo object (when called directly)
    if isinstance(timeout, typer.models.OptionInfo):
        timeout = timeout.default if hasattr(timeout, "default") else 30

    client = get_api_client(api_url, api_key)
    client.timeout = timeout  # Override timeout for status commands
    client.require_service_running()

    try:
        if name:
            response = client.get(f"/api/generators/{name}")
        else:
            # Use status endpoint for all generators
            response = client.get("/api/status")

        response.raise_for_status()
        data = response.json()

        if name:
            # Single generator details
            console.print(f"\n[bold]Generator: {data['name']}[/bold]\n")
            console.print(f"  [cyan]State:[/cyan] {data['state']}")
            console.print(f"  [cyan]Template:[/cyan] {data['template']}")
            console.print(f"  [cyan]Enabled:[/cyan] {'Yes' if data['enabled'] else 'No'}")
            if "timezone" in data and data["timezone"]:
                console.print(f"  [cyan]Timezone:[/cyan] {data['timezone']}")
            console.print(f"  [cyan]Base Rate:[/cyan] {data['frequency']['base_rate']} events/sec")
            console.print(
                f"  [cyan]Current Rate:[/cyan] {data['frequency']['current_rate']} events/sec"
            )
            console.print(f"  [cyan]Outputs:[/cyan] {', '.join(data['outputs'])}")

            stats = data["statistics"]
            console.print("\n  [bold]Statistics:[/bold]")
            console.print(f"    Events Generated: {stats['events_generated']}")
            console.print(f"    Errors: {stats['errors']}")
            console.print(f"    Uptime: {stats['uptime']}s")
            if stats.get("last_event"):
                console.print(f"    Last Event: {stats['last_event']}")

            # Display output handler status
            if "output_status" in data and data["output_status"]:
                console.print("\n  [bold]Output Status:[/bold]")
                for output in data["output_status"]:
                    handler_name = output.get("handler_name", "unknown")
                    handler_type = output.get("handler_type", "unknown")
                    health_status = output.get("health_status", "unknown")

                    # Determine health color
                    health_color = {
                        "healthy": "green",
                        "degraded": "yellow",
                        "failed": "red",
                    }.get(health_status, "white")

                    console.print(
                        f"    [{health_color}]{handler_name}[/{health_color}] ({handler_type}): {health_status.upper()}"
                    )

                    # Show detailed stats for HTTP handlers
                    if handler_type == "http":
                        if output.get("events_sent", 0) > 0 or output.get("events_failed", 0) > 0:
                            console.print(f"      Events Sent: {output.get('events_sent', 0)}")
                            console.print(f"      Events Failed: {output.get('events_failed', 0)}")
                            console.print(
                                f"      Batches: {output.get('batches_sent', 0)} sent, {output.get('batches_failed', 0)} failed"
                            )
                            if output.get("buffered_events", 0) > 0:
                                console.print(
                                    f"      [yellow]Buffered Events: {output['buffered_events']}[/yellow]"
                                )
                            if output.get("average_response_time_ms"):
                                console.print(
                                    f"      Avg Response Time: {output['average_response_time_ms']}ms"
                                )
                            if output.get("last_error_message"):
                                console.print(
                                    f"      [red]Last Error: {output['last_error_message']}[/red]"
                                )
                            if output.get("last_success_time"):
                                console.print(f"      Last Success: {output['last_success_time']}")
                            if output.get("last_failure_time"):
                                console.print(
                                    f"      [yellow]Last Failure: {output['last_failure_time']}[/yellow]"
                                )

                    # Show buffered events for any handler
                    elif output.get("buffered_events", 0) > 0:
                        console.print(
                            f"      [yellow]Buffered Events: {output['buffered_events']}[/yellow]"
                        )
        else:
            # All generators table
            table = Table(title="Generator Status")
            table.add_column("Name", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Template", style="yellow")
            table.add_column("Events", style="magenta")
            table.add_column("Errors", style="red")
            table.add_column("Uptime", style="blue")

            for gen in data.get("generators", []):
                # Handle both flattened (from /api/status) and nested (from /api/generators/{name}) formats
                if "statistics" in gen:
                    # Nested format (from individual generator endpoint)
                    stats = gen.get("statistics", {})
                    events = stats.get("events_generated", 0)
                    errors = stats.get("errors", 0)
                    uptime = stats.get("uptime")
                else:
                    # Flattened format (from /api/status endpoint)
                    events = gen.get("events_generated", 0)
                    errors = gen.get("errors", 0)
                    uptime = gen.get("uptime")

                uptime_str = f"{uptime}s" if uptime else "N/A"

                state_style = {
                    "RUNNING": "green",
                    "STOPPED": "dim",
                    "ERROR": "red",
                    "DEGRADED": "yellow",
                }.get(gen.get("state", "UNKNOWN"), "white")

                table.add_row(
                    gen.get("name", "unknown"),
                    f"[{state_style}]{gen.get('state', 'UNKNOWN')}[/{state_style}]",
                    gen.get("template", "unknown"),
                    str(events),
                    str(errors),
                    uptime_str,
                )

            console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
