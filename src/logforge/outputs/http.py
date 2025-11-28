"""HTTP output handler with batching."""

import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

from logforge.core.config import OutputDefinition, RetryConfig
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
        retry_config: Optional[RetryConfig] = None,
        buffer_size: int = 10000,
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
            retry_config: Retry configuration from global config
            buffer_size: Buffer size from global config
        """
        super().__init__(name, retry_config=retry_config, buffer_size=buffer_size)
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
        
        # Statistics tracking
        self._stats_lock = threading.Lock()
        self._events_sent = 0
        self._events_failed = 0
        self._batches_sent = 0
        self._batches_failed = 0
        self._connection_errors = 0
        self._http_errors = 0
        self._timeout_errors = 0
        self._auth_errors = 0
        self._total_bytes_sent = 0
        self._response_times: List[float] = []  # Keep last 100 response times
        self._last_success_time: Optional[float] = None
        self._last_failure_time: Optional[float] = None
        self._last_error_message: Optional[str] = None
        self._last_error_type: Optional[str] = None
        self._periodic_stats_time = time.time()
    
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
    def from_config(
        cls,
        definition: OutputDefinition,
        retry_config: Optional[RetryConfig] = None,
        buffer_size: int = 10000,
    ) -> 'HTTPOutputHandler':
        """Create handler from output definition.
        
        Args:
            definition: Output definition
            retry_config: Retry configuration from global config
            buffer_size: Buffer size from global config
            
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
            retry_config=retry_config,
            buffer_size=buffer_size,
        )
    
    def initialize(self) -> None:
        """Initialize handler and start batch timer."""
        logger.info(
            f"HTTP output '{self.name}' initialized: "
            f"URL={self.url}, method={self.method}, "
            f"batch_size={self.batch_size}, batch_interval={self.batch_interval}s, "
            f"timeout={self.timeout}s"
        )
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
            buffered_count = len(self._batch_buffer)
            
            # Log warning if buffer is getting full
            if buffered_count > self.buffer_size * 0.8:
                logger.warning(
                    f"HTTP output '{self.name}': Buffer is {buffered_count}/{self.buffer_size} "
                    f"({buffered_count/self.buffer_size*100:.1f}% full). "
                    f"Consider increasing batch_size or checking connection status."
                )
            
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
            else:
                return
        
        # Log periodic stats
        self._log_periodic_stats()
        
        # Send batch (outside lock)
        if events_to_send:
            self._send_batch(events_to_send)
    
    def _sanitize_header_value(self, key: str, value: str) -> str:
        """Sanitize sensitive header values for logging.
        
        Args:
            key: Header key
            value: Header value
            
        Returns:
            Sanitized value
        """
        key_lower = key.lower()
        if key_lower in ('authorization', 'x-api-key', 'x-auth-token'):
            # Redact tokens but keep prefix
            if value.startswith('Bearer '):
                return 'Bearer ***'
            elif value.startswith('Splunk '):
                return 'Splunk ***'
            elif value.startswith('Basic '):
                return 'Basic ***'
            else:
                return '***'
        return value
    
    def _truncate_response_body(self, body: str, max_length: int = 200) -> str:
        """Truncate response body for logging.
        
        Args:
            body: Response body string
            max_length: Maximum length
            
        Returns:
            Truncated body with ellipsis if needed
        """
        if len(body) <= max_length:
            return body
        return body[:max_length] + '...'
    
    def _send_batch(self, events: List[str]) -> None:
        """Send batch of events via HTTP.
        
        Args:
            events: List of event strings
            
        Raises:
            Exception: On send failure
        """
        start_time = time.time()
        event_count = len(events)
        
        try:
            logger.debug(
                f"HTTP output '{self.name}': Attempting to send batch of {event_count} events "
                f"to {self.url}"
            )
            
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
            
            # Log request details at DEBUG level
            if logger.isEnabledFor(10):  # DEBUG level
                sanitized_headers = {
                    k: self._sanitize_header_value(k, v)
                    for k, v in self._substituted_headers.items()
                }
                logger.debug(
                    f"HTTP output '{self.name}': Request headers: {sanitized_headers}"
                )
            
            # Send request
            response = requests.request(
                method=self.method,
                url=self.url,
                json=payload,
                headers=self._substituted_headers,
                timeout=self.timeout,
            )
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Check response status
            try:
                response.raise_for_status()
                
                # Success
                bytes_sent = len(response.content) if hasattr(response, 'content') else 0
                
                with self._stats_lock:
                    self._events_sent += event_count
                    self._batches_sent += 1
                    self._total_bytes_sent += bytes_sent
                    self._last_success_time = time.time()
                    # Keep last 100 response times
                    self._response_times.append(response_time)
                    if len(self._response_times) > 100:
                        self._response_times.pop(0)
                
                logger.info(
                    f"HTTP output '{self.name}': Successfully sent {event_count} events "
                    f"(status={response.status_code}, latency={response_time:.1f}ms, "
                    f"batch_size={event_count})"
                )
                
            except requests.HTTPError as e:
                # HTTP error (4xx, 5xx)
                response_time = (time.time() - start_time) * 1000
                status_code = response.status_code
                
                # Get response body for context
                try:
                    response_body = response.text[:500]  # First 500 chars
                except Exception:
                    response_body = "Unable to read response body"
                
                error_type = "HTTP_ERROR"
                is_auth_error = status_code in (401, 403)
                
                with self._stats_lock:
                    self._events_failed += event_count
                    self._batches_failed += 1
                    self._last_failure_time = time.time()
                    self._last_error_message = f"HTTP {status_code}: {response.reason}"
                    self._last_error_type = error_type
                    self._http_errors += 1
                    if is_auth_error:
                        self._auth_errors += 1
                
                # Log based on status code
                if is_auth_error:
                    logger.error(
                        f"HTTP output '{self.name}': Authentication failed: "
                        f"HTTP {status_code} {response.reason} - "
                        f"Response: {self._truncate_response_body(response_body)}"
                    )
                elif 400 <= status_code < 500:
                    logger.warning(
                        f"HTTP output '{self.name}': HTTP {status_code} client error: "
                        f"{response.reason} - Response: {self._truncate_response_body(response_body)}"
                    )
                else:  # 5xx
                    logger.warning(
                        f"HTTP output '{self.name}': HTTP {status_code} server error: "
                        f"{response.reason} - Response: {self._truncate_response_body(response_body)}"
                    )
                
                # Re-buffer events for retry
                with self._batch_lock:
                    self._batch_buffer.extend(events)
                
                raise
            
        except requests.exceptions.Timeout as e:
            # Timeout error
            response_time = (time.time() - start_time) * 1000
            error_msg = f"Request timeout after {self.timeout}s"
            
            with self._stats_lock:
                self._events_failed += event_count
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = error_msg
                self._last_error_type = "TIMEOUT"
                self._timeout_errors += 1
            
            logger.error(
                f"HTTP output '{self.name}': Request timeout after {self.timeout}s "
                f"(attempted to send {event_count} events)"
            )
            
            # Re-buffer events for retry
            with self._batch_lock:
                self._batch_buffer.extend(events)
            
            raise
        
        except requests.exceptions.ConnectionError as e:
            # Connection error
            error_msg = str(e)
            
            with self._stats_lock:
                self._events_failed += event_count
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"Connection failed: {error_msg}"
                self._last_error_type = "CONNECTION_ERROR"
                self._connection_errors += 1
            
            logger.error(
                f"HTTP output '{self.name}': Connection failed: {type(e).__name__} - "
                f"{error_msg} (attempted to send {event_count} events to {self.url})"
            )
            
            # Re-buffer events for retry
            with self._batch_lock:
                self._batch_buffer.extend(events)
            
            raise
        
        except requests.exceptions.RequestException as e:
            # Other request exceptions
            error_type = type(e).__name__
            error_msg = str(e)
            
            with self._stats_lock:
                self._events_failed += event_count
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"{error_type}: {error_msg}"
                self._last_error_type = error_type
                self._connection_errors += 1
            
            logger.error(
                f"HTTP output '{self.name}': Request failed: {error_type} - "
                f"{error_msg} (attempted to send {event_count} events)"
            )
            
            # Re-buffer events for retry
            with self._batch_lock:
                self._batch_buffer.extend(events)
            
            raise
        
        except Exception as e:
            # Unexpected errors
            error_type = type(e).__name__
            error_msg = str(e)
            
            with self._stats_lock:
                self._events_failed += event_count
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"{error_type}: {error_msg}"
                self._last_error_type = error_type
            
            logger.error(
                f"HTTP output '{self.name}': Unexpected error sending batch: {error_type} - "
                f"{error_msg} (attempted to send {event_count} events)",
                exc_info=True
            )
            
            # Re-buffer events for retry
            with self._batch_lock:
                self._batch_buffer.extend(events)
            
            raise
    
    def _retry_write(self) -> None:
        """Retry writing buffered events with HTTP-specific logging."""
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
                events_flushed = len(events_to_retry)
                with self._retry_lock:
                    attempts = self._retry_attempt
                    self._is_healthy = True
                    self._retry_attempt = 0
                
                logger.info(
                    f"HTTP output '{self.name}': Recovered after {attempts} retry attempts, "
                    f"flushed {events_flushed} buffered events"
                )
            else:
                # Some events still failing
                with self._retry_lock:
                    logger.warning(
                        f"HTTP output '{self.name}': Retry partially successful: "
                        f"{len(failed_events)}/{len(events_to_retry)} events still failing"
                    )
    
    def write_batch(self, events: List[str]) -> None:
        """Write batch of events.
        
        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)
    
    def get_statistics(self) -> Dict:
        """Get output handler statistics.
        
        Returns:
            Dictionary with statistics and health information
        """
        with self._stats_lock:
            # Calculate average response time
            avg_response_time = None
            if self._response_times:
                avg_response_time = sum(self._response_times) / len(self._response_times)
            
            # Determine health status
            health_status = "healthy"
            if self._last_failure_time:
                if self._last_success_time:
                    if self._last_failure_time > self._last_success_time:
                        health_status = "degraded"
                else:
                    health_status = "failed"
            
            # Calculate buffered events count
            with self._batch_lock:
                buffered_count = len(self._batch_buffer)
            
            stats = {
                "handler_name": self.name,
                "handler_type": "http",
                "url": self.url,
                "health_status": health_status,
                "events_sent": self._events_sent,
                "events_failed": self._events_failed,
                "batches_sent": self._batches_sent,
                "batches_failed": self._batches_failed,
                "buffered_events": buffered_count,
                "connection_errors": self._connection_errors,
                "http_errors": self._http_errors,
                "timeout_errors": self._timeout_errors,
                "auth_errors": self._auth_errors,
                "total_bytes_sent": self._total_bytes_sent,
                "average_response_time_ms": round(avg_response_time, 2) if avg_response_time else None,
                "last_success_time": (
                    datetime.utcfromtimestamp(self._last_success_time).isoformat() + "Z"
                    if self._last_success_time else None
                ),
                "last_failure_time": (
                    datetime.utcfromtimestamp(self._last_failure_time).isoformat() + "Z"
                    if self._last_failure_time else None
                ),
                "last_error_message": self._last_error_message,
                "last_error_type": self._last_error_type,
            }
        
        return stats
    
    def _log_periodic_stats(self) -> None:
        """Log periodic statistics (every 60 seconds)."""
        now = time.time()
        if now - self._periodic_stats_time < 60:
            return
        
        self._periodic_stats_time = now
        
        stats = self.get_statistics()
        
        # Only log if there's activity or issues
        if stats["events_sent"] > 0 or stats["events_failed"] > 0 or stats["buffered_events"] > 0:
            logger.info(
                f"HTTP output '{self.name}' statistics: "
                f"sent={stats['events_sent']}, failed={stats['events_failed']}, "
                f"batches={stats['batches_sent']}/{stats['batches_failed']}, "
                f"buffered={stats['buffered_events']}, "
                f"avg_latency={stats['average_response_time_ms']}ms, "
                f"health={stats['health_status']}"
            )
    
    def close(self) -> None:
        """Close handler and flush remaining batches."""
        # Log final statistics
        stats = self.get_statistics()
        logger.info(
            f"HTTP output '{self.name}' closing: "
            f"sent={stats['events_sent']} events, "
            f"failed={stats['events_failed']} events, "
            f"buffered={stats['buffered_events']} events remaining"
        )
        
        # Cancel timer
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None
        
        # Flush any remaining events
        self._flush_batch_if_ready(force=True)
