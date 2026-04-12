"""Path resolution and LOGFORGE_HOME management."""

import os
import pwd
import shutil
import sys
from pathlib import Path
from typing import Optional


def get_data_home_from_install_binary(bin_path: Path) -> Optional[Path]:
    """Return ``<install>/data`` when *bin_path* is under a known install layout.

    Used internally to locate the product root (parent of ``data``). Default
    ``LOGFORGE_HOME`` for the bundle is the **install root** (``/opt/logforge``), not this path.

    Resolution:
    - **Tarball / vendor**: any path with an ``opt`` segment followed by ``logforge`` →
      ``<.../opt/logforge>/data``
    - **Repo-style** (historical): ``…/<project>/bin/logforge`` where *project* is named
      ``logforge`` / ``LogForge`` → ``<project>/data``
    """
    try:
        resolved = bin_path.resolve()
    except OSError:
        return None

    parts = resolved.parts
    for i, name in enumerate(parts):
        if name.lower() != "logforge":
            continue
        if i > 0 and parts[i - 1].lower() == "opt":
            install_dir = Path(*parts[: i + 1])
            if install_dir.exists():
                return (install_dir / "data").resolve()

    if resolved.parent.parent.name.lower() == "logforge":
        install_dir = resolved.parent.parent
        if install_dir.exists():
            return (install_dir / "data").resolve()

    return None


def get_install_root_from_binary(bin_path: Path) -> Optional[Path]:
    """Return product/install root (parent of ``data``) for a bundled layout.

    For example ``/opt/logforge/app/bin/logforge`` → ``/opt/logforge``.
    """
    data_home = get_data_home_from_install_binary(bin_path)
    if data_home is None:
        return None
    return data_home.parent.resolve()


def _logforge_binary_candidates() -> list[Path]:
    """Paths to try when resolving bundle layout (``sudo`` often omits ``logforge`` from ``PATH``)."""
    raw: list[Path] = []
    if sys.argv and sys.argv[0]:
        a0 = Path(sys.argv[0])
        if a0.name.lower() == "logforge":
            raw.append(a0)
    w = shutil.which("logforge")
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


def get_bundle_home_from_install_binary(bin_path: Path) -> Optional[Path]:
    """Return default ``LOGFORGE_HOME`` for a tarball layout (product root, not ``…/data``).

    Official bundle under ``/opt/logforge`` uses **``/opt/logforge``** as the single state
    root (config, entities, templates, run, etc.); logs default to ``/opt/logforge/logs/``.
    """
    return get_install_root_from_binary(bin_path)


def default_application_log_file(bin_path: Optional[Path] = None) -> Path:
    """Default on-disk application log (Splunk-style: under install root).

    Uses ``<install_root>/logs/logforge.log`` when the binary is under a known
    bundle layout; otherwise ``<LOGFORGE_HOME>/logs/logforge.log``.
    """
    candidates: list[Path] = []
    if bin_path is not None:
        candidates.append(bin_path)
    else:
        candidates.extend(_logforge_binary_candidates())

    for c in candidates:
        try:
            resolved = c.resolve()
        except OSError:
            continue
        root = get_install_root_from_binary(resolved)
        if root is not None:
            return (root / "logs" / "logforge.log").resolve()

    return (get_logforge_home() / "logs" / "logforge.log").resolve()


def get_logforge_home() -> Path:
    """Resolve LOGFORGE_HOME directory (config/data root, not the app install path).

    Resolution order:
    1. LOGFORGE_HOME environment variable
    2. ./.logforge or ./logforge in current working directory (.logforge preferred)
    3. ../.logforge or ../logforge (parent directory)
    4. Official bundle: product root ``.../opt/logforge`` from the running binary
       (see :func:`get_bundle_home_from_install_binary`; uses ``sys.argv[0]`` and ``PATH``)
    5. ~/.logforge for interactive users (uid >= 1000)
    6. /opt/logforge for service accounts (uid < 1000) when no bundle home applies

    Returns:
        Path to LOGFORGE_HOME directory
    """
    # 1. Environment variable
    env_home = os.getenv('LOGFORGE_HOME')
    if env_home:
        home_path = Path(env_home).expanduser().resolve()
        _ensure_directory(home_path)
        return home_path

    cwd = Path.cwd()
    # 2. Local: prefer .logforge (repo/dev), then logforge (backward compat)
    for name in ('.logforge', 'logforge'):
        local_home = cwd / name
        if local_home.exists() and local_home.is_dir():
            return local_home.resolve()
    for name in ('.logforge', 'logforge'):
        parent_home = cwd.parent / name
        if parent_home.exists() and parent_home.is_dir():
            return parent_home.resolve()

    # 3. Bundle install: LOGFORGE_HOME = product root (/opt/logforge), not …/data
    try:
        for cand in _logforge_binary_candidates():
            try:
                resolved = cand.resolve()
            except OSError:
                continue
            bundle_home = get_bundle_home_from_install_binary(resolved)
            if bundle_home is not None:
                return bundle_home
    except Exception:
        pass

    # 4 & 5. Fallback: user or service
    try:
        uid = os.getuid()
        is_service_account = uid < 1000
    except (AttributeError, OSError):
        try:
            username = pwd.getpwuid(os.getuid()).pw_name
            is_service_account = username in ('logforge', 'logmgr', 'daemon', 'nobody')
        except (KeyError, AttributeError):
            is_service_account = False

    if is_service_account:
        home_path = Path('/opt/logforge')
    else:
        home_path = Path.home() / '.logforge'

    _ensure_directory(home_path)
    return home_path


def get_pidfile_path(home: Optional[Path] = None) -> Path:
    """Path to the main service PID file (LOGFORGE_HOME/run/logforge.pid)."""
    if home is None:
        home = get_logforge_home()
    return home.resolve() / "run" / "logforge.pid"


def _ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if needed.

    Args:
        path: Directory path to ensure
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise RuntimeError(f"Cannot create LOGFORGE_HOME directory {path}: {e}") from e


def validate_path_within_home(path: Path, home: Path) -> bool:
    """Validate that a path is within LOGFORGE_HOME.

    Args:
        path: Path to validate
        home: LOGFORGE_HOME base path

    Returns:
        True if path is within home, False otherwise
    """
    try:
        path_resolved = path.resolve()
        home_resolved = home.resolve()
        return path_resolved.is_relative_to(home_resolved)
    except (ValueError, AttributeError):
        # Python < 3.9 or path not relative
        try:
            return path_resolved == home_resolved or str(path_resolved).startswith(str(home_resolved) + os.sep)
        except Exception:
            return False


def get_config_path(home: Optional[Path] = None) -> Path:
    """Get path to config.yaml file.

    Args:
        home: LOGFORGE_HOME path. If None, resolves automatically.

    Returns:
        Path to config.yaml
    """
    if home is None:
        home = get_logforge_home()
    return home / 'config.yaml'


def get_entities_path(home: Optional[Path] = None) -> Path:
    """Get path to entities.yaml file.

    Args:
        home: LOGFORGE_HOME path. If None, resolves automatically.

    Returns:
        Path to entities.yaml
    """
    if home is None:
        home = get_logforge_home()
    return home / 'entities.yaml'


def get_templates_path(home: Optional[Path] = None) -> Path:
    """Get path to templates directory.

    Args:
        home: LOGFORGE_HOME path. If None, resolves automatically.

    Returns:
        Path to templates directory
    """
    if home is None:
        home = get_logforge_home()
    return home / 'templates'


def get_backups_path(home: Optional[Path] = None) -> Path:
    """Get path to backups directory.

    Args:
        home: LOGFORGE_HOME path. If None, resolves automatically.

    Returns:
        Path to backups directory
    """
    if home is None:
        home = get_logforge_home()
    backups_path = home / 'backups' / 'templates'
    _ensure_directory(backups_path)
    return backups_path

