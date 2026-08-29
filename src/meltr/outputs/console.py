"""Console output handler."""

import json
import sys
from typing import List, Optional

from meltr.core.config import OutputDefinition
from meltr.outputs.base import OutputHandler
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class ConsoleOutputHandler(OutputHandler):
    """Console output handler (stdout/stderr)."""
    
    def __init__(
        self,
        name: str,
        format: str = "json",
        stream: str = "stdout",
    ) -> None:
        """Initialize console output handler.
        
        Args:
            name: Handler name
            format: Output format ('json' or 'text')
            stream: Output stream ('stdout' or 'stderr')
        """
        super().__init__(name)
        self.format = format
        self.stream_name = stream
        self.stream = sys.stdout if stream == "stdout" else sys.stderr
    
    @classmethod
    def from_config(cls, definition: OutputDefinition) -> 'ConsoleOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            
        Returns:
            ConsoleOutputHandler instance
        """
        return cls(
            name=definition.name,
            format=definition.format or "json",
            stream=definition.stream or "stdout",
        )
    
    def _do_write(self, event: str) -> None:
        """Write event to console.
        
        Args:
            event: Event string
        """
        if self.format == "json":
            # Try to parse and pretty-print JSON, fall back to raw if not JSON
            try:
                data = json.loads(event)
                output = json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                output = event
            self.stream.write(output + '\n')
        else:
            # Text format
            self.stream.write(event)
            if not event.endswith('\n'):
                self.stream.write('\n')
        
        self.stream.flush()
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)
    
    def close(self) -> None:
        """Close handler (no-op for console)."""
        pass
