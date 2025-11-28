"""File output handler with rotation."""

import gzip
import shutil
from pathlib import Path
from typing import List, Optional

from logforge.core.config import OutputDefinition, OutputRotationConfig
from logforge.outputs.base import OutputHandler
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class FileOutputHandler(OutputHandler):
    """File output handler with size and time-based rotation."""
    
    def __init__(
        self,
        name: str,
        path: str,
        rotation: Optional[OutputRotationConfig] = None,
    ) -> None:
        """Initialize file output handler.
        
        Args:
            name: Handler name
            path: File path (supports {generator}, {date}, {timestamp} variables)
            rotation: Rotation configuration
        """
        super().__init__(name)
        self.path_template = path
        self.rotation = rotation
        self._file_handle = None
        self._current_path: Optional[Path] = None
        self._last_rotation_check = 0.0
    
    @classmethod
    def from_config(cls, definition: OutputDefinition) -> 'FileOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            
        Returns:
            FileOutputHandler instance
        """
        if not definition.path:
            raise ValueError(f"File output handler '{definition.name}' requires 'path'")
        
        return cls(
            name=definition.name,
            path=definition.path,
            rotation=definition.rotation,
        )
    
    def _resolve_path(self, generator_name: Optional[str] = None) -> Path:
        """Resolve file path with variable substitution.
        
        Args:
            generator_name: Generator name for {generator} substitution
            
        Returns:
            Resolved Path
        """
        import os
        import re
        from datetime import datetime
        
        path = self.path_template
        
        # Log original template for debugging
        logger.debug(f"Resolving path template: {path}")
        
        # Substitute LOGFORGE_HOME and other environment variables
        # LOGFORGE_HOME uses self-discovery if not set as env var
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name == 'LOGFORGE_HOME':
                # get_logforge_home() does self-discovery:
                # 1. Checks LOGFORGE_HOME env var
                # 2. Checks ./logforge, ../logforge
                # 3. Detects installation directory from binary location
                # 4. Falls back to ~/.logforge or /var/lib/logforge
                from logforge.core.paths import get_logforge_home
                home_path = str(get_logforge_home())
                logger.debug(f"Substituted ${var_name} with: {home_path}")
                return home_path
            env_value = os.getenv(var_name, match.group(0))
            if env_value != match.group(0):
                logger.debug(f"Substituted ${var_name} with: {env_value}")
            return env_value
        
        # Replace ${VAR} patterns
        pattern = r'\$\{([^}]+)\}'
        path = re.sub(pattern, replace_var, path)
        logger.debug(f"Path after substitution: {path}")
        
        # Substitute template variables
        if generator_name:
            path = path.replace('{generator}', generator_name)
        
        path = path.replace('{date}', datetime.now().strftime('%Y-%m-%d'))
        path = path.replace('{timestamp}', str(int(datetime.now().timestamp())))
        
        # Expand user home directory (~)
        path = os.path.expanduser(path)
        
        # Normalize path separators (handle Windows-style backslashes)
        # Replace backslashes with forward slashes for cross-platform compatibility
        path = path.replace('\\', '/')
        
        # Create Path object
        path_obj = Path(path)
        
        # If path is relative, try to resolve it
        # Check if it starts with a known pattern that suggests it should be absolute
        if not path_obj.is_absolute():
            # If path still contains ${LOGFORGE_HOME} or looks like a template variable, log warning
            if '${' in str(path_obj) or path_obj.parts[0] == 'logforge':
                # This suggests substitution didn't happen - try to resolve relative to LOGFORGE_HOME
                from logforge.core.paths import get_logforge_home
                home = get_logforge_home()
                # If path starts with 'logforge', remove it and use home directly
                if path_obj.parts[0] == 'logforge':
                    path_obj = home / Path(*path_obj.parts[1:])
                else:
                    path_obj = home / path_obj
                logger.warning(f"Path was relative, resolved relative to LOGFORGE_HOME: {path_obj}")
            else:
                # Resolve relative to current working directory
                path_obj = Path.cwd() / path_obj
        
        # Resolve to absolute path (follows symlinks, normalizes)
        try:
            path_obj = path_obj.resolve()
        except (OSError, RuntimeError):
            # If resolve fails (e.g., path doesn't exist yet), just make it absolute
            if not path_obj.is_absolute():
                path_obj = Path.cwd() / path_obj
        
        logger.debug(f"Final resolved path: {path_obj}")
        return path_obj
    
    def initialize(self) -> None:
        """Initialize file handler."""
        # Path will be resolved on first write with generator name
        pass
    
    def _do_write(self, event: str) -> None:
        """Write event to file.
        
        Args:
            event: Event string
        """
        # TODO: Resolve path with generator name from context
        # For now, use path as-is
        file_path = self._resolve_path()
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file if needed
        if self._current_path != file_path or self._file_handle is None:
            if self._file_handle:
                self._file_handle.close()
            self._file_handle = open(file_path, 'a', encoding='utf-8')
            self._current_path = file_path
        
        # Check rotation
        if self.rotation:
            self._check_rotation(file_path)
        
        # Write event
        self._file_handle.write(event)
        if not event.endswith('\n'):
            self._file_handle.write('\n')
        self._file_handle.flush()
    
    def _check_rotation(self, file_path: Path) -> None:
        """Check if file needs rotation.
        
        Args:
            file_path: Current file path
        """
        if not file_path.exists():
            return
        
        if self.rotation.type == 'size':
            max_size = self._parse_size(self.rotation.max_size)
            if file_path.stat().st_size >= max_size:
                self._rotate_file(file_path)
        elif self.rotation.type == 'time':
            # TODO: Implement time-based rotation
            pass
    
    def _rotate_file(self, file_path: Path) -> None:
        """Rotate file.
        
        Args:
            file_path: File to rotate
        """
        import time
        
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        # Find next rotation number
        rotation_num = 1
        while (file_path.parent / f"{file_path.name}.{rotation_num}").exists():
            rotation_num += 1
        
        rotated_path = file_path.parent / f"{file_path.name}.{rotation_num}"
        shutil.move(str(file_path), str(rotated_path))
        
        # Compress if configured
        if self.rotation.compress:
            with open(rotated_path, 'rb') as f_in:
                with gzip.open(f"{rotated_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            rotated_path.unlink()
        
        logger.info(f"Rotated file: {file_path} -> {rotated_path}")
    
    def _parse_size(self, size: Optional[str]) -> int:
        """Parse size string to bytes."""
        if isinstance(size, int):
            return size
        if not size:
            return 100 * 1024 * 1024  # 100MB default
        
        size = size.upper()
        multipliers = {'KB': 1024, 'MB': 1024*1024, 'GB': 1024*1024*1024}
        
        for unit, mult in multipliers.items():
            if size.endswith(unit):
                return int(size[:-len(unit)]) * mult
        
        return int(size)
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)
    
    def close(self) -> None:
        """Close file handle."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

