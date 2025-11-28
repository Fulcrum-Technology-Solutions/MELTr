"""HTTP output handler with batching."""

import json
import os
import re
import threading
import time
from typing import Dict, List, Optional

import requests

from logforge.core.config import OutputDefinition
from logforge.outputs.base import OutputHandler
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class HTTPOutputHandler(OutputHandler):
    """HTTP output handler with event batching."""
    
    def __init__(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        batch_size: int = 100,
        batch_interval: int = 5,
        timeout: int = 30,
    ) -> None:
        """Initialize HTTP output handler.
        
        Args:
            name: Handler name
            url: Target URL
            method: HTTP method (default: POST)
            headers: HTTP headers (supports ${VAR} substitution)
            batch_size: Events per batch
            batch_interval: Seconds between batch sends
            timeout: Request timeout in seconds
        """
        super().__init__(name)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.timeout = timeout
        
        # Batch buffer
        self._batch_buffer: List[str] = []
        self._batch_lock = threading.Lock()
        self._last_batch_time = time.time()
        self._batch_timer: Optional[threading.Timer] = None
        
        # Substitute environment variables in headers
        self._substituted_headers = self._substitute_env_vars(self.headers)
    
    def _substitute_env_vars(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Substitute environment variables in header values.
        
        Args:
            headers: Headers dictionary
            
        Returns:
            Headers with environment variables substituted
        """
        substituted = {}
        for key, value in headers.items():
            # Replace ${VAR_NAME} with environment variable
            def replace_var(match: re.Match) -> str:
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))
            
            pattern = r'\$\{([^}]+)\}'
            substituted[key] = re.sub(pattern, replace_var, value)
        
        return substituted
    
    @classmethod
    def from_config(cls, definition: OutputDefinition) -> 'HTTPOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            
        Returns:
            HTTPOutputHandler instance
        """
        if not definition.url:
            raise ValueError(f"HTTP output handler '{definition.name}' requires 'url'")
        
        return cls(
            name=definition.name,
            url=definition.url,
            method=definition.method or "POST",
            headers=definition.headers,
            batch_size=definition.batch_size or 100,
            batch_interval=definition.batch_interval or 5,
            timeout=definition.timeout or 30,
        )
    
    def initialize(self) -> None:
        """Initialize handler and start batch timer."""
        # Start periodic batch flush timer
        self._start_batch_timer()
    
    def _start_batch_timer(self) -> None:
        """Start timer for periodic batch sends."""
        if self._batch_timer:
            self._batch_timer.cancel()
        
        self._batch_timer = threading.Timer(
            self.batch_interval,
            self._flush_batch_timer
        )
        self._batch_timer.daemon = True
        self._batch_timer.start()
    
    def _flush_batch_timer(self) -> None:
        """Flush batch when timer expires."""
        self._flush_batch_if_ready(force=True)
        # Restart timer
        self._start_batch_timer()
    
    def _do_write(self, event: str) -> None:
        """Write event to batch buffer.
        
        Args:
            event: Event string
        """
        with self._batch_lock:
            self._batch_buffer.append(event)
            
            # Check if batch is full
            if len(self._batch_buffer) >= self.batch_size:
                self._flush_batch_if_ready(force=True)
            else:
                # Check if interval elapsed
                self._flush_batch_if_ready(force=False)
    
    def _flush_batch_if_ready(self, force: bool = False) -> None:
        """Flush batch if ready (size or interval).
        
        Args:
            force: Force flush even if conditions not met
        """
        with self._batch_lock:
            if not self._batch_buffer:
                return
            
            current_time = time.time()
            time_elapsed = current_time - self._last_batch_time >= self.batch_interval
            
            if force or len(self._batch_buffer) >= self.batch_size or time_elapsed:
                events_to_send = list(self._batch_buffer)
                self._batch_buffer.clear()
                self._last_batch_time = current_time
        
        # Send batch (outside lock)
        if events_to_send:
            self._send_batch(events_to_send)
    
    def _send_batch(self, events: List[str]) -> None:
        """Send batch of events via HTTP.
        
        Args:
            events: List of event strings
        """
        try:
            # Parse events as JSON (if they're JSON strings)
            json_events = []
            for event in events:
                try:
                    json_events.append(json.loads(event))
                except (json.JSONDecodeError, TypeError):
                    # Not JSON, send as string
                    json_events.append(event)
            
            # Wrap in array if multiple events
            if len(json_events) > 1:
                payload = json_events
            else:
                payload = json_events[0] if json_events else {}
            
            # Send request
            response = requests.request(
                method=self.method,
                url=self.url,
                json=payload,
                headers=self._substituted_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            logger.debug(f"HTTP output {self.name}: Sent batch of {len(events)} events")
            
        except Exception as e:
            logger.error(f"HTTP output {self.name}: Failed to send batch: {e}")
            # Re-buffer events for retry
            with self._batch_lock:
                self._batch_buffer.extend(events)
            raise
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)
    
    def close(self) -> None:
        """Close handler and flush remaining batches."""
        # Cancel timer
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None
        
        # Flush any remaining events
        self._flush_batch_if_ready(force=True)
