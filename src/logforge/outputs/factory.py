"""Output handler factory."""

from typing import Dict, List, Optional

from logforge.core.config import OutputDefinition, OutputsConfig, RetryConfig
from logforge.outputs.base import OutputHandler
from logforge.outputs.console import ConsoleOutputHandler
from logforge.outputs.file import FileOutputHandler
from logforge.outputs.http import HTTPOutputHandler
from logforge.outputs.syslog import SyslogOutputHandler
from logforge.outputs.tcp import TCPOutputHandler
from logforge.utils.logging import get_logger

logger = get_logger(__name__)

# Handler type registry
HANDLER_TYPES: Dict[str, type] = {
    'file': FileOutputHandler,
    'console': ConsoleOutputHandler,
    'http': HTTPOutputHandler,
    'tcp': TCPOutputHandler,
    'syslog': SyslogOutputHandler,
}


def create_output_handlers(
    output_names: List[str],
    output_definitions: List[OutputDefinition],
    retry_config: Optional[RetryConfig] = None,
    buffer_size: int = 10000,
) -> List[OutputHandler]:
    """Create output handlers from names and definitions.
    
    Args:
        output_names: List of output handler names
        output_definitions: List of output definitions from config
        retry_config: Retry configuration (from config.outputs.retry)
        buffer_size: Buffer size (from config.outputs.buffer_size)
        
    Returns:
        List of OutputHandler instances
    """
    handlers = []
    definitions_by_name = {defn.name: defn for defn in output_definitions}
    
    for name in output_names:
        if name not in definitions_by_name:
            logger.warning(f"Output definition not found: {name}")
            continue
        
        definition = definitions_by_name[name]
        handler_type = HANDLER_TYPES.get(definition.type)
        
        if not handler_type:
            logger.warning(f"Unknown output handler type: {definition.type}")
            continue
        
        try:
            handler = handler_type.from_config(definition)
            
            # Set retry config and buffer size if handler supports it
            if hasattr(handler, 'retry_config'):
                handler.retry_config = retry_config
            if hasattr(handler, 'buffer_size'):
                handler.buffer_size = buffer_size
            
            handlers.append(handler)
            logger.debug(f"Created output handler: {name} (type: {definition.type})")
        except Exception as e:
            logger.error(f"Failed to create output handler {name}: {e}", exc_info=True)
    
    return handlers

