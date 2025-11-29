"""File output handler with rotation."""

import gzip
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from logforge.core.config import OutputDefinition, OutputRotationConfig
from logforge.outputs.base import OutputHandler
from logforge.outputs.path_resolver import PathTemplateContext, resolve_path_template
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
            path: File path template (supports {generator}, {vendor}, {product}, {date}, etc.)
            rotation: Rotation configuration
        """
        super().__init__(name)
        self.path_template = path
        self.rotation = rotation
        self._file_handle = None
        self._current_path: Optional[Path] = None
        self._last_rotation_check = 0.0
        self._path_context: Optional[PathTemplateContext] = None
        self._resolved_path_cache: Optional[Path] = None
        self._last_path_resolution_time = 0.0
    
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
    
    def set_template_context(
        self,
        generator_name: str,
        output_name: str,
        template_metadata: Optional[Dict[str, Any]] = None,
        organization_name: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> None:
        """Set template context for path resolution.
        
        Args:
            generator_name: Generator name
            output_name: Output handler name
            template_metadata: Template metadata dict (vendor, product, data_source, etc.)
            organization_name: Organization name from entity registry
            timezone: Timezone string (e.g., 'America/New_York'). Defaults to UTC if not provided.
        """
        self._path_context = PathTemplateContext(
            generator_name=generator_name,
            output_name=output_name,
            template_metadata=template_metadata,
            organization_name=organization_name,
            timezone=timezone or 'UTC',
        )
        # Clear cache when context changes
        self._resolved_path_cache = None
    
    def _resolve_path(self, force_refresh: bool = False) -> Path:
        """Resolve file path with variable substitution.
        
        Args:
            force_refresh: Force re-resolution even if cached (for time-based rotation)
            
        Returns:
            Resolved Path
        """
        # Check if we need to re-resolve (for time-based templates)
        now = time.time()
        needs_refresh = (
            force_refresh or
            self._resolved_path_cache is None or
            self._last_path_resolution_time == 0 or
            # Re-resolve if template contains time variables and enough time has passed
            ('{date}' in self.path_template or '{hour}' in self.path_template or '{timestamp}' in self.path_template)
            and (now - self._last_path_resolution_time) > 60  # Re-check every minute
        )
        
        if not needs_refresh and self._resolved_path_cache:
            return self._resolved_path_cache
        
        # If no context set, use fallback resolution
        if not self._path_context:
            logger.warning(f"FileOutputHandler '{self.name}': No template context set, using fallback resolution")
            # Fallback: create minimal context with UTC timezone
            # This maintains backward compatibility
            self._path_context = PathTemplateContext(
                generator_name="unknown",
                output_name=self.name,
                timezone='UTC',
            )
        
        # Resolve path using template resolver
        resolved_path = resolve_path_template(
            self.path_template,
            self._path_context,
            sanitize=True,
        )
        
        # Cache the resolved path
        self._resolved_path_cache = resolved_path
        self._last_path_resolution_time = now
        
        return resolved_path
    
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
        
        # Check if time-based template variables have changed
        # This applies to both size and time-based rotation when path contains time variables
        if self._path_context:
            # Re-resolve path to see if it changed (for time-based templates)
            new_path = self._resolve_path(force_refresh=True)
            if new_path != file_path:
                # Time variable changed, rotate current file and switch to new path
                self._rotate_file(file_path)
                # Clear cache and current path to force new file on next write
                self._current_path = None
                self._resolved_path_cache = None
                return
        
        # Check rotation based on type
        if self.rotation.type == 'size':
            max_size = self._parse_size(self.rotation.max_size)
            if file_path.stat().st_size >= max_size:
                self._rotate_file(file_path)
        elif self.rotation.type == 'time':
            # Time-based rotation: check if max_age has been exceeded
            max_age_seconds = self._parse_time_interval(self.rotation.max_age)
            if max_age_seconds:
                file_age = time.time() - file_path.stat().st_mtime
                if file_age >= max_age_seconds:
                    self._rotate_file(file_path)
    
    def _rotate_file(self, file_path: Path) -> None:
        """Rotate file.
        
        Args:
            file_path: File to rotate
        """
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        if not file_path.exists():
            return
        
        # Determine rotated filename pattern
        # For time-based rotation with date/hour in template, use timestamp-based naming
        # For size-based rotation, use sequential numbering
        if self.rotation.type == 'time' and self._path_context:
            # Use timestamp-based naming for time rotations
            # Use timezone from path context if available, otherwise UTC
            if self._path_context:
                now_dt = self._path_context._now
            else:
                from zoneinfo import ZoneInfo
                now_dt = datetime.now(ZoneInfo('UTC'))
            timestamp = now_dt.strftime('%Y%m%d-%H%M%S')
            base_name = file_path.stem
            rotated_path = file_path.parent / f"{base_name}.{timestamp}{file_path.suffix}"
        else:
            # Sequential numbering for size-based rotation
            rotation_num = 1
            while (file_path.parent / f"{file_path.name}.{rotation_num}").exists():
                rotation_num += 1
            rotated_path = file_path.parent / f"{file_path.name}.{rotation_num}"
        
        # Move file to rotated location
        shutil.move(str(file_path), str(rotated_path))
        
        # Compress if configured
        if self.rotation.compress:
            with open(rotated_path, 'rb') as f_in:
                with gzip.open(f"{rotated_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            rotated_path.unlink()
            rotated_path = Path(f"{rotated_path}.gz")
        
        # Clean up old rotated files if max_files is configured
        if self.rotation.max_files:
            self._cleanup_old_rotations(file_path.parent, file_path.name, self.rotation.max_files)
        
        logger.info(f"Rotated file: {file_path} -> {rotated_path}")
    
    def _cleanup_old_rotations(self, directory: Path, base_name: str, max_files: int) -> None:
        """Clean up old rotated files, keeping only the most recent N files.
        
        Args:
            directory: Directory containing rotated files
            base_name: Base filename pattern
            max_files: Maximum number of rotated files to keep
        """
        # Find all rotated files matching the pattern
        rotated_files = []
        for file in directory.glob(f"{base_name}.*"):
            if file.name != base_name:  # Exclude current file
                rotated_files.append(file)
        
        # Sort by modification time (newest first)
        rotated_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Remove files beyond max_files limit
        for old_file in rotated_files[max_files:]:
            try:
                old_file.unlink()
                logger.debug(f"Removed old rotated file: {old_file}")
            except OSError as e:
                logger.warning(f"Failed to remove old rotated file {old_file}: {e}")
    
    def _parse_time_interval(self, interval: Optional[str]) -> Optional[int]:
        """Parse time interval string to seconds.
        
        Args:
            interval: Time interval string (e.g., "7d", "24h", "30m")
            
        Returns:
            Number of seconds, or None if invalid
        """
        if not interval:
            return None
        
        interval = interval.lower().strip()
        
        # Parse number and unit
        multipliers = {
            's': 1,
            'sec': 1,
            'second': 1,
            'seconds': 1,
            'm': 60,
            'min': 60,
            'minute': 60,
            'minutes': 60,
            'h': 3600,
            'hr': 3600,
            'hour': 3600,
            'hours': 3600,
            'd': 86400,
            'day': 86400,
            'days': 86400,
        }
        
        for unit, mult in multipliers.items():
            if interval.endswith(unit):
                try:
                    num = int(interval[:-len(unit)])
                    return num * mult
                except ValueError:
                    return None
        
        # Try to parse as integer (assume seconds)
        try:
            return int(interval)
        except ValueError:
            logger.warning(f"Invalid time interval format: {interval}")
            return None
    
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

