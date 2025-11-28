"""Syslog output handler (RFC 5424 and RFC 3164)."""

import socket
import threading
from datetime import datetime
from typing import List, Optional

from logforge.core.config import OutputDefinition
from logforge.outputs.base import OutputHandler
from logforge.utils.logging import get_logger

logger = get_logger(__name__)

# Syslog facility codes
FACILITIES = {
    'kern': 0, 'user': 1, 'mail': 2, 'daemon': 3, 'auth': 4, 'syslog': 5,
    'lpr': 6, 'news': 7, 'uucp': 8, 'cron': 9, 'authpriv': 10, 'ftp': 11,
    'local0': 16, 'local1': 17, 'local2': 18, 'local3': 19,
    'local4': 20, 'local5': 21, 'local6': 22, 'local7': 23,
}

# Syslog severity codes
SEVERITIES = {
    'emerg': 0, 'alert': 1, 'crit': 2, 'err': 3,
    'warning': 4, 'notice': 5, 'info': 6, 'debug': 7,
}


class SyslogOutputHandler(OutputHandler):
    """Syslog output handler supporting RFC 5424 and RFC 3164."""
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int = 514,
        protocol: str = "udp",
        facility: str = "local0",
        severity: str = "info",
        format: str = "rfc5424",
    ) -> None:
        """Initialize syslog output handler.
        
        Args:
            name: Handler name
            host: Syslog server host
            port: Syslog server port
            protocol: Protocol ('tcp' or 'udp')
            facility: Syslog facility
            severity: Syslog severity
            format: Format ('rfc5424' or 'rfc3164')
        """
        super().__init__(name)
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self.facility = facility.lower()
        self.severity = severity.lower()
        self.format = format.lower()
        
        # Validate
        if self.facility not in FACILITIES:
            raise ValueError(f"Invalid syslog facility: {facility}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Invalid syslog severity: {severity}")
        if self.format not in ('rfc5424', 'rfc3164'):
            raise ValueError(f"Invalid syslog format: {format}")
        
        # Calculate PRI value
        self.pri = (FACILITIES[self.facility] * 8) + SEVERITIES[self.severity]
        
        # Socket
        self._socket: Optional[socket.socket] = None
        self._socket_lock = threading.Lock()
        self._hostname = socket.gethostname()
    
    @classmethod
    def from_config(cls, definition: OutputDefinition) -> 'SyslogOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            
        Returns:
            SyslogOutputHandler instance
        """
        if not definition.host:
            raise ValueError(f"Syslog output handler '{definition.name}' requires 'host'")
        
        return cls(
            name=definition.name,
            host=definition.host,
            port=definition.port or 514,
            protocol=definition.protocol or "udp",
            facility=definition.facility or "local0",
            severity=definition.severity or "info",
            format=definition.format or "rfc5424",
        )
    
    def _get_socket(self) -> socket.socket:
        """Get or create socket.
        
        Returns:
            Socket instance
        """
        with self._socket_lock:
            if self._socket:
                return self._socket
            
            if self.protocol == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self._socket = sock
            return sock
    
    def _format_rfc5424(self, message: str) -> str:
        """Format message as RFC 5424.
        
        Args:
            message: Message content
            
        Returns:
            RFC 5424 formatted syslog message
        """
        now = datetime.utcnow()
        timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        # RFC 5424 format: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
        return (
            f"<{self.pri}>1 {timestamp} {self._hostname} logforge - - - {message}"
        )
    
    def _format_rfc3164(self, message: str) -> str:
        """Format message as RFC 3164.
        
        Args:
            message: Message content
            
        Returns:
            RFC 3164 formatted syslog message
        """
        now = datetime.now()
        timestamp = now.strftime('%b %d %H:%M:%S')
        
        # RFC 3164 format: <PRI>TIMESTAMP HOSTNAME TAG: MSG
        tag = "logforge"
        return f"<{self.pri}>{timestamp} {self._hostname} {tag}: {message}"
    
    def _do_write(self, event: str) -> None:
        """Write event as syslog message.
        
        Args:
            event: Event string
        """
        # Format message
        if self.format == "rfc5424":
            message = self._format_rfc5424(event)
        else:
            message = self._format_rfc3164(event)
        
        # Send via socket
        sock = self._get_socket()
        sock.sendto(message.encode('utf-8'), (self.host, self.port))
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)
    
    def close(self) -> None:
        """Close socket."""
        with self._socket_lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

