"""Logging setup and configuration."""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from logforge.core.config import Config


def setup_logging(config: Optional[Config] = None, log_level: Optional[str] = None) -> None:
    """Configure application logging based on config or defaults.
    
    Args:
        config: Configuration object with logging settings. If None, uses defaults.
        log_level: Override log level from config. If None, uses config value.
    """
    if config and hasattr(config, 'logging'):
        level = log_level or getattr(config.logging, 'level', 'INFO')
        log_file = getattr(config.logging, 'file', None)
        rotation_config = getattr(config.logging, 'rotation', None)
        format_str = getattr(config.logging, 'format', 
                           '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        level = log_level or os.getenv('LOGFORGE_LOG_LEVEL', 'INFO')
        log_file = os.getenv('LOGFORGE_LOG_FILE', None)
        rotation_config = None
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger('logforge')
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_str)
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        if rotation_config:
            max_size = getattr(rotation_config, 'max_size', 50 * 1024 * 1024)  # 50MB default
            backup_count = getattr(rotation_config, 'backup_count', 5)
            
            # Parse max_size if string (e.g., "50MB")
            if isinstance(max_size, str):
                max_size = _parse_size(max_size)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
        
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def _parse_size(size_str: str) -> int:
    """Parse size string like '50MB' to bytes.
    
    Args:
        size_str: Size string with unit (e.g., '50MB', '1GB', '100KB')
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    multipliers = {
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
    }
    
    for unit, multiplier in multipliers.items():
        if size_str.endswith(unit):
            number = int(size_str[:-len(unit)])
            return number * multiplier
    
    # Default to bytes if no unit
    return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f'logforge.{name}')

