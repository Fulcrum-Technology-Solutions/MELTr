"""API server management CLI commands."""

from typing import Optional

import typer
from rich.console import Console

from logforge.service import LogForgeService

app = typer.Typer(name="api", help="API server management")
console = Console()


@app.command("start")
def api_start(
    host: Optional[str] = typer.Option(None, "--host", help="API server host"),
    port: Optional[int] = typer.Option(None, "--port", help="API server port"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Start the LogForge API server and service."""
    from pathlib import Path
    
    config_path = Path(config) if config else None
    
    try:
        service = LogForgeService(config_path=config_path)
        
        if host:
            service.config.api.host = host
        if port:
            service.config.api.port = port
        
        service.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

