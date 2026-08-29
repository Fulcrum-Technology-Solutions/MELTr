"""Pipeline management CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from meltr.cli.api_client import get_api_client

app = typer.Typer(name="pipelines", help="Pipeline management")
console = Console()


@app.command("list")
def pipelines_list(
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """List all pipelines."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.get("/api/pipelines")
        response.raise_for_status()
        data = response.json()

        table = Table(title="Pipelines")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Streams", style="yellow")
        table.add_column("Enabled", style="magenta")

        for pipeline in sorted(data["pipelines"], key=lambda item: item["name"].lower()):
            state_style = {
                "RUNNING": "green",
                "STOPPED": "dim",
                "ERROR": "red",
                "DEGRADED": "yellow",
                "STARTING": "blue",
                "STOPPING": "yellow",
            }.get(pipeline["state"], "white")

            table.add_row(
                pipeline["name"],
                f"[{state_style}]{pipeline['state']}[/{state_style}]",
                str(len(pipeline.get("streams", []))),
                "✓" if pipeline.get("enabled") else "✗",
            )

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("start")
def pipelines_start(
    name: str = typer.Argument(..., help="Pipeline name"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Start a pipeline."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.post(f"/api/pipelines/{name}/start", json={})
        response.raise_for_status()
        data = response.json()

        console.print(f"[green]✓ {data['message']}[/green]")
        console.print(f"  Pipeline: {name}")
        console.print(f"  State: {data['state']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("stop")
def pipelines_stop(
    name: str = typer.Argument(..., help="Pipeline name"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Stop a pipeline."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        response = client.post(f"/api/pipelines/{name}/stop", json={})
        response.raise_for_status()
        data = response.json()

        console.print(f"[green]✓ {data['message']}[/green]")
        console.print(f"  Pipeline: {name}")
        console.print(f"  State: {data['state']}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("status")
def pipelines_status(
    name: str | None = typer.Argument(None, help="Pipeline name (optional)"),
    api_url: str | None = typer.Option(None, "--api-url", envvar="MELTR_API_URL"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="MELTR_API_KEY"),
) -> None:
    """Show pipeline status."""
    client = get_api_client(api_url, api_key)
    client.require_service_running()

    try:
        if name:
            response = client.get(f"/api/pipelines/{name}")
        else:
            response = client.get("/api/pipelines")

        response.raise_for_status()
        data = response.json()

        if name:
            console.print(f"\n[bold]Pipeline: {data['name']}[/bold]\n")
            console.print(f"  [cyan]State:[/cyan] {data['state']}")
            console.print(f"  [cyan]Enabled:[/cyan] {'Yes' if data['enabled'] else 'No'}")
            console.print(f"  [cyan]Outputs:[/cyan] {', '.join(data['outputs'])}")
            console.print(f"  [cyan]Schedule:[/cyan] {data['schedule']['mode']}")
            stats = data["statistics"]
            console.print("\n  [bold]Statistics:[/bold]")
            console.print(f"    Events Generated: {stats['events_generated']}")
            console.print(f"    Errors: {stats['errors']}")

            if data.get("streams"):
                table = Table(title="Streams")
                table.add_column("Generator", style="cyan")
                table.add_column("Template", style="yellow")
                table.add_column("State", style="green")
                table.add_column("Events", style="magenta")
                for stream in data["streams"]:
                    table.add_row(
                        stream["name"],
                        stream["template"],
                        stream["state"],
                        str(stream["events_generated"]),
                    )
                console.print(table)
        else:
            table = Table(title="Pipeline Status")
            table.add_column("Name", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Streams", style="yellow")
            table.add_column("Events", style="magenta")

            for pipeline in data.get("pipelines", []):
                table.add_row(
                    pipeline["name"],
                    pipeline["state"],
                    str(len(pipeline.get("streams", []))),
                    str(pipeline["statistics"]["events_generated"]),
                )
            console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
