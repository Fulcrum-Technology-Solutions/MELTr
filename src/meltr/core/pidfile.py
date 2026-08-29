"""PID file for tarball / CLI-managed LogForge daemon (logforge stop)."""

import os
import sys
from pathlib import Path

from meltr.core.paths import get_pidfile_path


def write_service_pidfile(pid: int | None = None, home: Path | None = None) -> Path:
    """Create run/ and write the current (or given) PID."""
    pid = pid or os.getpid()
    path = get_pidfile_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid) + "\n", encoding="ascii")
    return path


def read_service_pid(home: Path | None = None) -> int | None:
    """Read PID from file, or None if missing/unreadable."""
    path = get_pidfile_path(home)
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        return None


def remove_service_pidfile(home: Path | None = None) -> None:
    """Unconditionally remove the PID file if present."""
    path = get_pidfile_path(home)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def cmdline_suggests_logforge(pid: int) -> bool:
    """Best-effort check that pid is a LogForge service (Linux /proc)."""
    if sys.platform != "linux":
        return True
    proc = Path(f"/proc/{pid}/cmdline")
    try:
        raw = proc.read_bytes()
    except (OSError, FileNotFoundError):
        return False
    cmd = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").lower()
    return "logforge" in cmd
