"""Dashboard rendering should not crash when all generator uptimes are 0."""

from rich.console import Console

from logforge.cli.dashboard import render_status_snapshot


def test_render_status_snapshot_does_not_divide_by_zero_when_uptime_is_zero():
    fake_data = {
        "system": {"cpu_percent": 0.0, "memory_mb": 0, "threads": 1},
        "uptime": 0,
        "generators": [
            {"name": "gen1", "state": "STOPPED", "events_generated": 10, "errors": 0, "uptime": 0},
        ],
    }

    layout = render_status_snapshot(fake_data, refresh_count=1)
    assert layout is not None


def test_render_status_snapshot_total_row_markup_is_valid():
    """Regression: TOTAL row rich tags must have matching close tags."""
    fake_data = {
        "system": {"cpu_percent": 0.0, "memory_mb": 0, "threads": 1},
        "uptime": 0,
        "generators": [
            {"name": "gen1", "state": "STOPPED", "events_generated": 10, "errors": 0, "uptime": 0},
        ],
    }

    layout = render_status_snapshot(fake_data, refresh_count=1)
    console = Console()
    # Rich will raise MarkupError here if any generated markup is invalid.
    console.render_lines(layout, console.options)

