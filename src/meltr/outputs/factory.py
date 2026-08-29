"""Output handler factory."""

from typing import Dict, List, Optional

from meltr.core.config import OutputDefinition, OutputsConfig, RetryConfig
from meltr.outputs.base import OutputHandler
from meltr.outputs.console import ConsoleOutputHandler
from meltr.outputs.file import FileOutputHandler
from meltr.outputs.http import HTTPOutputHandler
from meltr.outputs.syslog import SyslogOutputHandler
from meltr.outputs.tcp import TCPOutputHandler
from meltr.utils.logging import get_logger

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
            # Pass retry_config and buffer_size to from_config if supported
            if hasattr(handler_type, 'from_config'):
                # Check if from_config accepts retry_config and buffer_size parameters
                import inspect
                sig = inspect.signature(handler_type.from_config)
                params = list(sig.parameters.keys())
                
                if 'retry_config' in params and 'buffer_size' in params:
                    handler = handler_type.from_config(definition, retry_config=retry_config, buffer_size=buffer_size)
                else:
                    handler = handler_type.from_config(definition)
                    # Fallback: Set as attributes if handler doesn't accept them in from_config
                    if hasattr(handler, 'retry_config'):
                        handler.retry_config = retry_config
                    if hasattr(handler, 'buffer_size'):
                        handler.buffer_size = buffer_size
            else:
                raise ValueError(f"Handler type {handler_type} does not have from_config method")
            
            handlers.append(handler)
            logger.debug(f"Created output handler: {name} (type: {definition.type})")
        except Exception as e:
            logger.error(f"Failed to create output handler {name}: {e}", exc_info=True)
    
    return handlers

