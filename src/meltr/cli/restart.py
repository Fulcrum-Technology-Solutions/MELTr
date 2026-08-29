"""Restart helpers for the top-level `logforge restart` command."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

import typer
from rich.console import Console


def systemd_unit_exists(unit: str = "meltr.service") -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        res = subprocess.run(
            ["systemctl", "list-unit-files", unit],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return unit in (res.stdout or "")
    except Exception:
        return False


def systemd_restart(unit: str = "meltr.service") -> bool:
    try:
        res = subprocess.run(
            ["systemctl", "restart", unit],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def restart(
    *,
    timeout: int,
    foreground: bool,
    console: Console,
    unit: str = "meltr.service",
    api_stop: Callable[..., None],
    api_start: Callable[..., None],
) -> None:
    """Restart LogForge via systemd if possible, else local PID-file stop/start."""
    if systemd_unit_exists(unit) and systemd_restart(unit):
        console.print("[green]✓ Restarted via systemd[/green]")
        return

    console.print("[dim]ℹ systemd not available or restart failed; restarting locally[/dim]")

    try:
        api_stop(timeout=timeout)
    except typer.Exit as e:
        # api_stop may exit(0) when already stopped / no PID found.
        code = getattr(e, "exit_code", getattr(e, "code", 0))
        if code not in (0, None):
            raise

    api_start(foreground=foreground)
