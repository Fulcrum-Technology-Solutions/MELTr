"""Path resolution and LOGFORGE_HOME management."""

import os
import pwd
from pathlib import Path
from typing import Optional


def get_logforge_home() -> Path:
    """Resolve LOGFORGE_HOME directory (config/data root, not the app install path).

    Resolution order:
    1. LOGFORGE_HOME environment variable
    2. ./.logforge or ./logforge in current working directory (.logforge preferred)
    3. ../.logforge or ../logforge (parent directory)
    4. Installation directory: when binary is under /opt/LogForge or /opt/logforge, use <install>/data
    5. ~/.logforge for interactive users (uid >= 1000)
    6. /var/lib/logforge for service accounts (uid < 1000)

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

    # 3. Install dir: /opt/LogForge or /opt/logforge → <install>/data (no duplicative .../logforge)
    try:
        import shutil
        bin_path = shutil.which('logforge')
        if bin_path:
            bin_path = Path(bin_path).resolve()
            bin_str = str(bin_path).lower()
            if '/opt/logforge' in bin_str:
                opt = Path('/opt')
                if opt.exists():
                    install_dir = next((opt / p.name for p in opt.iterdir() if p.name.lower() == 'logforge'), Path('/opt/logforge'))
                    if install_dir.exists():
                        return (install_dir / 'data').resolve()
            # Repo-style: .../LogForge/.venv/bin/logforge or .../logforge/.venv/bin/logforge
            if bin_path.parent.parent.name.lower() == 'logforge':
                install_dir = bin_path.parent.parent
                if install_dir.exists():
                    return (install_dir / 'data').resolve()
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
        home_path = Path('/var/lib/logforge')
    else:
        home_path = Path.home() / '.logforge'

    _ensure_directory(home_path)
    return home_path


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

