"""Path resolution and LOGFORGE_HOME management."""

import os
import pwd
from pathlib import Path
from typing import Optional


def get_logforge_home() -> Path:
    """Resolve LOGFORGE_HOME directory.
    
    Resolution order (like Splunk/Cribl):
    1. LOGFORGE_HOME environment variable
    2. ./logforge in current working directory
    3. ../logforge (parent directory)
    4. Installation directory detection (from binary location)
    5. ~/.logforge for interactive users (uid >= 1000)
    6. /var/lib/logforge for service accounts (uid < 1000)
    
    Returns:
        Path to LOGFORGE_HOME directory
    """
    # Check environment variable first
    env_home = os.getenv('LOGFORGE_HOME')
    if env_home:
        home_path = Path(env_home).expanduser().resolve()
        _ensure_directory(home_path)
        return home_path
    
    # Check for local logforge directory (current directory)
    cwd = Path.cwd()
    local_home = cwd / 'logforge'
    if local_home.exists() and local_home.is_dir():
        return local_home.resolve()
    
    # Check parent directory (common for project layouts)
    parent_home = cwd.parent / 'logforge'
    if parent_home.exists() and parent_home.is_dir():
        return parent_home.resolve()
    
    # Try to detect installation directory from binary location
    try:
        import shutil
        bin_path = shutil.which('logforge')
        if bin_path:
            bin_path = Path(bin_path).resolve()
            # If binary is in /opt/logforge/.venv/bin/logforge, use /opt/logforge/logforge
            if '/opt/logforge' in str(bin_path):
                install_dir = Path('/opt/logforge')
                home = install_dir / 'logforge'
                if home.exists() or install_dir.exists():
                    return home.resolve()
            # If binary is in something like /path/to/logforge/.venv/bin/logforge
            elif bin_path.parent.parent.name == 'logforge':
                install_dir = bin_path.parent.parent
                home = install_dir / 'logforge'
                if home.exists() or install_dir.exists():
                    return home.resolve()
    except Exception:
        pass
    
    # Fall back to traditional locations
    # Determine if running as service account
    try:
        uid = os.getuid()
        is_service_account = uid < 1000
    except (AttributeError, OSError):
        # Windows or other platform without getuid
        # Check for specific service user names
        try:
            username = pwd.getpwuid(os.getuid()).pw_name
            is_service_account = username in ('logforge', 'daemon', 'nobody')
        except (KeyError, AttributeError):
            # Default to user home if can't determine
            is_service_account = False
    
    if is_service_account:
        # For service accounts, try /opt/logforge/logforge first (common installation)
        opt_home = Path('/opt/logforge/logforge')
        if opt_home.parent.exists():
            return opt_home.resolve()
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

