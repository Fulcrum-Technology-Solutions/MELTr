"""Generator management CLI commands."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from logforge.cli.api_client import get_api_client

app = typer.Typer(name="generators", help="Generator management")
console = Console()


@app.command("list")
def generators_list(
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """List all generators."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()
    
    try:
        response = client.get("/api/generators")
        response.raise_for_status()
        data = response.json()
        
        table = Table(title="Generators")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Template", style="yellow")
        table.add_column("Enabled", style="magenta")
        
        for gen in data["generators"]:
            state_style = {
                "RUNNING": "green",
                "STOPPED": "dim",
                "ERROR": "red",
                "DEGRADED": "yellow",
                "STARTING": "blue",
                "STOPPING": "yellow",
            }.get(gen["state"], "white")
            
            table.add_row(
                gen["name"],
                f"[{state_style}]{gen['state']}[/{state_style}]",
                gen["template"],
                "✓" if gen["enabled"] else "✗",
            )
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("start")
def generators_start(
    name: str = typer.Argument(..., help="Generator name"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
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
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
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
    name: str = typer.Argument(..., help="Generator name"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
) -> None:
    """Restart a generator."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()
    
    try:
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
    name: Optional[str] = typer.Argument(None, help="Generator name (optional)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", envvar="LOGFORGE_API_URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="LOGFORGE_API_KEY"),
    timeout: int = typer.Option(30, "--timeout", help="Request timeout in seconds"),
) -> None:
    """Show generator status."""
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
            console.print(f"  [cyan]Base Rate:[/cyan] {data['frequency']['base_rate']} events/sec")
            console.print(f"  [cyan]Current Rate:[/cyan] {data['frequency']['current_rate']} events/sec")
            console.print(f"  [cyan]Outputs:[/cyan] {', '.join(data['outputs'])}")
            
            stats = data['statistics']
            console.print(f"\n  [bold]Statistics:[/bold]")
            console.print(f"    Events Generated: {stats['events_generated']}")
            console.print(f"    Errors: {stats['errors']}")
            console.print(f"    Uptime: {stats['uptime']}s")
            if stats.get('last_event'):
                console.print(f"    Last Event: {stats['last_event']}")
            
            # Display output handler status
            if 'output_status' in data and data['output_status']:
                console.print(f"\n  [bold]Output Status:[/bold]")
                for output in data['output_status']:
                    handler_name = output.get('handler_name', 'unknown')
                    handler_type = output.get('handler_type', 'unknown')
                    health_status = output.get('health_status', 'unknown')
                    
                    # Determine health color
                    health_color = {
                        'healthy': 'green',
                        'degraded': 'yellow',
                        'failed': 'red',
                    }.get(health_status, 'white')
                    
                    console.print(f"    [{health_color}]{handler_name}[/{health_color}] ({handler_type}): {health_status.upper()}")
                    
                    # Show detailed stats for HTTP handlers
                    if handler_type == 'http':
                        if output.get('events_sent', 0) > 0 or output.get('events_failed', 0) > 0:
                            console.print(f"      Events Sent: {output.get('events_sent', 0)}")
                            console.print(f"      Events Failed: {output.get('events_failed', 0)}")
                            console.print(f"      Batches: {output.get('batches_sent', 0)} sent, {output.get('batches_failed', 0)} failed")
                            if output.get('buffered_events', 0) > 0:
                                console.print(f"      [yellow]Buffered Events: {output['buffered_events']}[/yellow]")
                            if output.get('average_response_time_ms'):
                                console.print(f"      Avg Response Time: {output['average_response_time_ms']}ms")
                            if output.get('last_error_message'):
                                console.print(f"      [red]Last Error: {output['last_error_message']}[/red]")
                            if output.get('last_success_time'):
                                console.print(f"      Last Success: {output['last_success_time']}")
                            if output.get('last_failure_time'):
                                console.print(f"      [yellow]Last Failure: {output['last_failure_time']}[/yellow]")
                    
                    # Show buffered events for any handler
                    elif output.get('buffered_events', 0) > 0:
                        console.print(f"      [yellow]Buffered Events: {output['buffered_events']}[/yellow]")
        else:
            # All generators table
            table = Table(title="Generator Status")
            table.add_column("Name", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Template", style="yellow")
            table.add_column("Events", style="magenta")
            table.add_column("Errors", style="red")
            table.add_column("Uptime", style="blue")
            
            for gen in data.get('generators', []):
                stats = gen.get('statistics', {})
                uptime_str = f"{stats.get('uptime', 0)}s" if stats.get('uptime') else "N/A"
                
                state_style = {
                    "RUNNING": "green",
                    "STOPPED": "dim",
                    "ERROR": "red",
                    "DEGRADED": "yellow",
                }.get(gen['state'], "white")
                
                table.add_row(
                    gen['name'],
                    f"[{state_style}]{gen['state']}[/{state_style}]",
                    gen['template'],
                    str(stats.get('events_generated', 0)),
                    str(stats.get('errors', 0)),
                    uptime_str,
                )
            
            console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

