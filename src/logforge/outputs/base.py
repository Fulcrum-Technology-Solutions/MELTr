"""Base output handler abstract class with retry and buffering."""

import os
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import List, Optional

from logforge.core.config import RetryConfig
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class OutputHandler(ABC):
    """Abstract base class for output handlers with retry and buffering."""
    
    def __init__(
        self,
        name: str,
        retry_config: Optional[RetryConfig] = None,
        buffer_size: int = 10000,
    ) -> None:
        """Initialize output handler.
        
        Args:
            name: Handler name
            retry_config: Retry configuration
            buffer_size: Maximum buffer size for events
        """
        self.name = name
        self.retry_config = retry_config
        self.buffer_size = buffer_size
        
        # Event buffer
        self._buffer: deque = deque(maxlen=buffer_size)
        self._buffer_lock = threading.Lock()
        
        # Retry state
        self._retry_attempt = 0
        self._last_failure_time: Optional[float] = None
        self._is_healthy = True
        self._retry_lock = threading.Lock()
    
    def write(self, event: str) -> None:
        """Write a single event with retry and buffering.
        
        Args:
            event: Event string to write
        """
        try:
            self._write_internal(event)
            # Success - reset retry state
            with self._retry_lock:
                self._retry_attempt = 0
                self._is_healthy = True
                # Flush buffer if we were recovering
                if self._buffer:
                    self._flush_buffer()
        except Exception as e:
            self._handle_write_error(event, e)
    
    def _write_internal(self, event: str) -> None:
        """Internal write method (to be implemented by subclasses).
        
        Args:
            event: Event string to write
            
        Raises:
            Exception: On write failure
        """
        self._do_write(event)
    
    @abstractmethod
    def _do_write(self, event: str) -> None:
        """Perform actual write operation (implemented by subclasses).
        
        Args:
            event: Event string to write
            
        Raises:
            Exception: On write failure
        """
        pass
    
    def _handle_write_error(self, event: str, error: Exception) -> None:
        """Handle write error with retry and buffering.
        
        Args:
            event: Event that failed to write
            error: Exception that occurred
        """
        error_type = type(error).__name__
        is_transient = self._is_transient_error(error)
        
        if not is_transient:
            # Permanent error - log and drop event
            logger.error(f"Output handler {self.name}: Permanent error: {error}")
            return
        
        # Transient error - buffer and retry
        with self._buffer_lock:
            if len(self._buffer) >= self.buffer_size:
                # Buffer full - drop oldest
                dropped = self._buffer.popleft()
                logger.warning(
                    f"Output handler {self.name}: Buffer full, dropping event. "
                    f"Buffer size: {self.buffer_size}"
                )
            self._buffer.append(event)
        
        with self._retry_lock:
            self._is_healthy = False
            self._last_failure_time = time.time()
            
            # Check if we should retry
            if self.retry_config and self.retry_config.max_attempts != 0:
                if (self.retry_config.max_attempts > 0 and
                    self._retry_attempt >= self.retry_config.max_attempts):
                    logger.error(
                        f"Output handler {self.name}: Max retry attempts reached"
                    )
                    return
            
            # Calculate backoff
            backoff = self._calculate_backoff()
            self._retry_attempt += 1
            
            logger.warning(
                f"Output handler {self.name}: Write failed, retry {self._retry_attempt} "
                f"in {backoff:.1f}s: {error}"
            )
            
            # Schedule retry
            threading.Timer(backoff, self._retry_write).start()
    
    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if error is transient.
        
        Args:
            error: Exception to check
            
        Returns:
            True if transient, False if permanent
        """
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # Network errors are transient
        if any(keyword in error_str for keyword in ['connection', 'timeout', 'network', 'unreachable']):
            return True
        
        # Permission errors are permanent
        if any(keyword in error_str for keyword in ['permission', 'access denied', 'forbidden']):
            return False
        
        # File system errors
        if 'no space' in error_str or 'disk full' in error_str:
            return True  # Could be temporary
        
        if 'permission denied' in error_str:
            return False
        
        # Default: assume transient for network-based handlers, permanent for file-based
        return True
    
    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay.
        
        Returns:
            Backoff delay in seconds
        """
        if not self.retry_config:
            return 5.0
        
        base_interval = self.retry_config.retry_interval
        multiplier = self.retry_config.backoff_multiplier
        max_backoff = self.retry_config.max_backoff
        
        backoff = base_interval * (multiplier ** (self._retry_attempt - 1))
        return min(backoff, max_backoff)
    
    def _retry_write(self) -> None:
        """Retry writing buffered events."""
        with self._buffer_lock:
            if not self._buffer:
                return
            events_to_retry = list(self._buffer)
        
        # Try to write all buffered events
        failed_events = []
        for event in events_to_retry:
            try:
                self._write_internal(event)
            except Exception as e:
                failed_events.append(event)
        
        with self._buffer_lock:
            # Update buffer with failed events
            self._buffer.clear()
            self._buffer.extend(failed_events)
            
            if not failed_events:
                # All events written successfully
                with self._retry_lock:
                    self._is_healthy = True
                    self._retry_attempt = 0
                logger.info(f"Output handler {self.name}: Recovered, buffer flushed")
    
    def _flush_buffer(self) -> None:
        """Flush all buffered events."""
        with self._buffer_lock:
            events = list(self._buffer)
            self._buffer.clear()
        
        for event in events:
            try:
                self._write_internal(event)
            except Exception as e:
                # Re-buffer if still failing
                with self._buffer_lock:
                    if len(self._buffer) < self.buffer_size:
                        self._buffer.append(event)
    
    @abstractmethod
    def write_batch(self, events: List[str]) -> None:
        """Write a batch of events.
        
        Args:
            events: List of event strings to write
            
        Raises:
            Exception: On write failure
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        pass
    
    def initialize(self) -> None:
        """Initialize handler (optional override)."""
        pass
    
    def is_healthy(self) -> bool:
        """Check if handler is healthy.
        
        Returns:
            True if healthy, False if degraded
        """
        with self._retry_lock:
            return self._is_healthy
