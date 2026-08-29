"""TCP output handler."""

import socket
import threading
from typing import List, Optional

from meltr.core.config import OutputDefinition
from meltr.outputs.base import OutputHandler
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class TCPOutputHandler(OutputHandler):
    """TCP socket output handler."""
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        delimiter: str = "\n",
        keepalive: bool = True,
    ) -> None:
        """Initialize TCP output handler.
        
        Args:
            name: Handler name
            host: Target host
            port: Target port
            delimiter: Event delimiter
            keepalive: Enable TCP keepalive
        """
        super().__init__(name)
        self.host = host
        self.port = port
        self.delimiter = delimiter
        self.keepalive = keepalive
        
        self._socket: Optional[socket.socket] = None
        self._socket_lock = threading.Lock()
    
    @classmethod
    def from_config(cls, definition: OutputDefinition) -> 'TCPOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            
        Returns:
            TCPOutputHandler instance
        """
        if not definition.host or not definition.port:
            raise ValueError(f"TCP output handler '{definition.name}' requires 'host' and 'port'")
        
        return cls(
            name=definition.name,
            host=definition.host,
            port=definition.port,
            delimiter=definition.delimiter or "\n",
            keepalive=definition.keepalive if definition.keepalive is not None else True,
        )
    
    def _connect(self) -> None:
        """Establish TCP connection."""
        if self._socket:
            try:
                # Test if socket is still connected
                self._socket.getpeername()
                return
            except (OSError, AttributeError):
                # Socket closed, need to reconnect
                self._socket = None
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            if self.keepalive:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            sock.settimeout(10.0)  # Connection timeout
            sock.connect((self.host, self.port))
            sock.settimeout(None)  # Remove timeout after connection
            
            self._socket = sock
            logger.info(f"TCP output {self.name}: Connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"TCP output {self.name}: Connection failed: {e}")
            raise
    
    def _do_write(self, event: str) -> None:
        """Write event to TCP socket.
        
        Args:
            event: Event string
        """
        with self._socket_lock:
            # Ensure connected
            self._connect()
            
            # Send event with delimiter
            message = event + self.delimiter
            self._socket.sendall(message.encode('utf-8'))
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        with self._socket_lock:
            # Ensure connected
            self._connect()
            
            # Send all events
            for event in events:
                message = event + self.delimiter
                self._socket.sendall(message.encode('utf-8'))
    
    def close(self) -> None:
        """Close TCP connection."""
        with self._socket_lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            logger.debug(f"TCP output {self.name}: Connection closed")

