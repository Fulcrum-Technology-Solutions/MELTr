"""Path resolution and MELTR_HOME management."""

from __future__ import annotations

import os
import pwd
import shutil
import sys
from pathlib import Path


def get_data_home_from_install_binary(bin_path: Path) -> Path | None:
    """Return ``<install>/data`` when *bin_path* is under a known install layout.

    Resolution:
    - Tarball / vendor: ``…/opt/meltr`` → ``…/data``
    - Repo-style: ``…/<project>/bin/meltr`` where project is ``meltr`` → ``<project>/data``
    """
    try:
        resolved = bin_path.resolve()
    except OSError:
        return None

    parts = resolved.parts
    for i, name in enumerate(parts):
        if name.lower() != "meltr":
            continue
        if i > 0 and parts[i - 1].lower() == "opt":
            install_dir = Path(*parts[: i + 1])
            if install_dir.exists():
                return (install_dir / "data").resolve()

    parent_project = resolved.parent.parent.name.lower()
    if parent_project == "meltr":
        install_dir = resolved.parent.parent
        if install_dir.exists():
            return (install_dir / "data").resolve()

    return None


def get_install_root_from_binary(bin_path: Path) -> Path | None:
    """Return product/install root (parent of ``data``) for a bundled layout."""
    data_home = get_data_home_from_install_binary(bin_path)
    if data_home is None:
        return None
    return data_home.parent.resolve()


def _meltr_binary_candidates() -> list[Path]:
    """Paths to try when resolving bundle layout."""
    raw: list[Path] = []
    if sys.argv and sys.argv[0]:
        a0 = Path(sys.argv[0])
        if a0.name.lower() == "meltr":
            raw.append(a0)
    for cmd in ("meltr",):
        w = shutil.which(cmd)
        if w:
            raw.append(Path(w))
    seen: set[str] = set()
    out: list[Path] = []
    for p in raw:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out




def get_bundle_home_from_install_binary(bin_path: Path) -> Path | None:
    """Return default home for a tarball layout (product root, not ``…/data``)."""
    return get_install_root_from_binary(bin_path)


def default_application_log_file(bin_path: Path | None = None) -> Path:
    """Default on-disk application log under install root or MELTR_HOME."""
    candidates: list[Path] = []
    if bin_path is not None:
        candidates.append(bin_path)
    else:
        candidates.extend(_meltr_binary_candidates())

    for c in candidates:
        try:
            resolved = c.resolve()
        except OSError:
            continue
        root = get_install_root_from_binary(resolved)
        if root is not None:
            return (root / "logs" / "meltr.log").resolve()

    return (get_meltr_home() / "logs" / "meltr.log").resolve()


def get_meltr_home() -> Path:
    """Resolve MELTR_HOME directory (config/data root).

    Resolution order:
    1. MELTR_HOME environment variable
    2. ./.meltr or ./meltr in cwd (and parent)
    3. Official bundle product root from running binary
    4. ~/.meltr for interactive users
    5. /opt/meltr for service accounts
    """
    env_home = os.getenv("MELTR_HOME")
    if env_home:
        home_path = Path(env_home).expanduser().resolve()
        _ensure_directory(home_path)
        return home_path

    cwd = Path.cwd()
    for name in (".meltr", "meltr"):
        local_home = cwd / name
        if local_home.exists() and local_home.is_dir():
            return local_home.resolve()
    for name in (".meltr", "meltr"):
        parent_home = cwd.parent / name
        if parent_home.exists() and parent_home.is_dir():
            return parent_home.resolve()

    try:
        for cand in _meltr_binary_candidates():
            try:
                resolved = cand.resolve()
            except OSError:
                continue
            bundle_home = get_bundle_home_from_install_binary(resolved)
            if bundle_home is not None:
                return bundle_home
    except Exception:
        pass

    try:
        uid = os.getuid()
        is_service_account = uid < 1000
    except (AttributeError, OSError):
        try:
            username = pwd.getpwuid(os.getuid()).pw_name
            is_service_account = username in ("meltr", "logmgr", "daemon", "nobody")
        except (KeyError, AttributeError):
            is_service_account = False

    if is_service_account:
        home_path = Path("/opt/meltr")
    else:
        home_path = Path.home() / ".meltr"

    _ensure_directory(home_path)
    return home_path


# Compat alias used by transitional code / Enterprise
get_meltr_home = get_meltr_home


def get_pidfile_path(home: Path | None = None) -> Path:
    """Path to the main service PID file (MELTR_HOME/run/meltr.pid)."""
    if home is None:
        home = get_meltr_home()
    return home.resolve() / "run" / "meltr.pid"


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise RuntimeError(f"Cannot create MELTR_HOME directory {path}: {e}") from e


def validate_path_within_home(path: Path, home: Path) -> bool:
    try:
        path_resolved = path.resolve()
        home_resolved = home.resolve()
        return path_resolved.is_relative_to(home_resolved)
    except (ValueError, AttributeError):
        try:
            return path_resolved == home_resolved or str(path_resolved).startswith(
                str(home_resolved) + os.sep
            )
        except Exception:
            return False


def get_config_path(home: Path | None = None) -> Path:
    if home is None:
        home = get_meltr_home()
    return home / "config.yaml"


def get_entities_path(home: Path | None = None) -> Path:
    if home is None:
        home = get_meltr_home()
    return home / "entities.yaml"


def get_templates_path(home: Path | None = None) -> Path:
    if home is None:
        home = get_meltr_home()
    return home / "templates"


def get_backups_path(home: Path | None = None) -> Path:
    if home is None:
        home = get_meltr_home()
    backups_path = home / "backups" / "templates"
    _ensure_directory(backups_path)
    return backups_path
