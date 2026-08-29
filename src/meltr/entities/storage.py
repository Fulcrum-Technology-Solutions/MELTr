"""Entity storage and persistence layer."""

import gzip
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from meltr.core.paths import get_entities_path, validate_path_within_home
from meltr.entities.validator import validate_entities, _validate_entities_structure
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class EntityStorage:
    """Manages entity file persistence with auto-save and backups."""
    
    def __init__(
        self,
        entities_path: Optional[Path] = None,
        auto_save: bool = True,
        save_interval: int = 60,
        backup_enabled: bool = True,
        backup_count: int = 3,
    ) -> None:
        """Initialize entity storage.
        
        Args:
            entities_path: Path to entities.yaml. If None, uses default.
            auto_save: Enable automatic periodic saves
            save_interval: Seconds between auto-saves
            backup_enabled: Enable backup creation
            backup_count: Number of backups to keep
        """
        self.entities_path = entities_path or get_entities_path()
        self.auto_save = auto_save
        self.save_interval = save_interval
        self.backup_enabled = backup_enabled
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._last_save_time = 0.0
        self._auto_save_thread: Optional[threading.Thread] = None
        self._stop_auto_save = threading.Event()
    
    def load(self, strict: bool = True) -> Dict[str, Any]:
        """Load entities from YAML file.
        
        Args:
            strict: If True, requires at least one entity of each type. If False, allows empty lists.
        
        Returns:
            Dictionary with organization, users, devices, services
            
        Raises:
            FileNotFoundError: If entities file doesn't exist
            ValueError: If file is invalid
        """
        if not self.entities_path.exists():
            raise FileNotFoundError(f"Entities file not found: {self.entities_path}")
        
        try:
            with self.entities_path.open('r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in entities file: {e}") from e
        
        if not isinstance(data, dict):
            raise ValueError("Entities file must contain a YAML mapping/object")
        
        # Validate schema (with strictness based on flag)
        if strict:
            validate_entities(data)
        else:
            # Loose validation - just check structure, not content
            _validate_entities_structure(data)
        
        return data
    
    def save(self, data: Dict[str, Any], create_backup: bool = True) -> None:
        """Save entities to YAML file.
        
        Args:
            data: Entity data dictionary
            create_backup: Whether to create backup before saving
        """
        with self._lock:
            # Validate before saving
            validate_entities(data)
            
            # Create backup if enabled
            if create_backup and self.backup_enabled:
                self._create_backup()
            
            # Write to temporary file first (atomic write)
            temp_path = self.entities_path.with_suffix('.yaml.tmp')
            try:
                with temp_path.open('w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
                # Atomic move
                temp_path.replace(self.entities_path)
                
                # Set secure permissions (600)
                self.entities_path.chmod(0o600)
                
                self._last_save_time = time.time()
                logger.debug(f"Saved entities to {self.entities_path}")
            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(f"Failed to save entities: {e}") from e
    
    def _create_backup(self) -> None:
        """Create backup of current entities file."""
        if not self.entities_path.exists():
            return
        
        # Rotate existing backups
        for i in range(self.backup_count, 0, -1):
            old_backup = self.entities_path.with_suffix(f'.yaml.{i}')
            new_backup = self.entities_path.with_suffix(f'.yaml.{i + 1}')
            
            if old_backup.exists():
                if i == self.backup_count:
                    # Compress and remove oldest backup
                    with old_backup.open('rb') as f_in:
                        with gzip.open(f'{old_backup}.gz', 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    old_backup.unlink()
                else:
                    old_backup.replace(new_backup)
        
        # Create new backup
        backup_path = self.entities_path.with_suffix('.yaml.1')
        shutil.copy2(self.entities_path, backup_path)
        backup_path.chmod(0o600)
        logger.debug(f"Created backup: {backup_path}")
    
    def load_backup(self, backup_number: int = 1) -> Optional[Dict[str, Any]]:
        """Load entities from backup file.
        
        Args:
            backup_number: Backup number (1 = most recent)
            
        Returns:
            Entity data or None if backup doesn't exist
        """
        backup_path = self.entities_path.with_suffix(f'.yaml.{backup_number}')
        
        # Try compressed backup
        if not backup_path.exists():
            compressed_path = Path(f'{backup_path}.gz')
            if compressed_path.exists():
                # Decompress to temp location
                temp_path = backup_path.with_suffix('.yaml.tmp')
                with gzip.open(compressed_path, 'rb') as f_in:
                    with temp_path.open('wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path = temp_path
        
        if not backup_path.exists():
            return None
        
        try:
            with backup_path.open('r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load backup {backup_number}: {e}")
            return None
    
    def start_auto_save(self, get_data_func) -> None:
        """Start auto-save thread.
        
        Args:
            get_data_func: Function that returns current entity data to save
        """
        if not self.auto_save or self._auto_save_thread is not None:
            return
        
        def auto_save_loop() -> None:
            """Auto-save loop."""
            while not self._stop_auto_save.wait(self.save_interval):
                try:
                    data = get_data_func()
                    if data:
                        self.save(data, create_backup=False)  # Don't backup on every auto-save
                except Exception as e:
                    logger.error(f"Auto-save failed: {e}", exc_info=True)
        
        self._stop_auto_save.clear()
        self._auto_save_thread = threading.Thread(
            target=auto_save_loop,
            daemon=True,
            name="entity-auto-save"
        )
        self._auto_save_thread.start()
        logger.info(f"Started auto-save thread (interval: {self.save_interval}s)")
    
    def stop_auto_save(self) -> None:
        """Stop auto-save thread."""
        if self._auto_save_thread is None:
            return
        
        self._stop_auto_save.set()
        if self._auto_save_thread.is_alive():
            self._auto_save_thread.join(timeout=2.0)
        self._auto_save_thread = None
        logger.info("Stopped auto-save thread")

