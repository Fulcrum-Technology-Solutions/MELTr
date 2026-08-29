"""HTTP output handler with batching and streaming."""

import concurrent.futures
import json
import os
import queue
import re
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from meltr.core.config import OutputDefinition, RetryConfig
from meltr.outputs.base import OutputHandler
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class HTTPOutputHandler(OutputHandler):
    """HTTP output handler with event batching and streaming."""

    def __init__(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        batch_size: int = 100,
        batch_interval: int = 5,
        timeout: int = 30,
        retry_config: RetryConfig | None = None,
        buffer_size: int = 10000,
        streaming: bool = True,
        overflow_policy: str = "drop_newest",
    ) -> None:
        """Initialize HTTP output handler.

        Args:
            name: Handler name
            url: Target URL
            method: HTTP method (default: POST)
            headers: HTTP headers (supports ${VAR} substitution)
            batch_size: Events per batch (ignored if streaming=True)
            batch_interval: Seconds between batch sends (ignored if streaming=True)
            timeout: Request timeout in seconds
            retry_config: Retry configuration from global config
            buffer_size: Buffer size from global config
            streaming: If True, send events individually as generated. If False, batch events.
            overflow_policy: When retry queue is full, drop_newest or drop_oldest.
        """
        super().__init__(name, retry_config=retry_config, buffer_size=buffer_size)
        self.overflow_policy = overflow_policy
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.timeout = timeout
        self.streaming = streaming

        # Batch buffer - use thread-safe queue instead of list with lock to prevent deadlocks
        # Queue is thread-safe and non-blocking for single operations
        self._batch_buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._last_batch_time = time.time()
        self._batch_timer: threading.Timer | None = None

        # Background thread pool for non-blocking HTTP requests (streaming mode)
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        if streaming:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=5, thread_name_prefix=f"http-{name}"  # Configurable if needed
            )

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
        self._response_times: list[float] = []  # Keep last 100 response times
        self._last_success_time: float | None = None
        self._last_failure_time: float | None = None
        self._last_error_message: str | None = None
        self._last_error_type: str | None = None
        self._periodic_stats_time = time.time()
        self._batch_buffer_dropped = 0
        self.timezone: str = "UTC"  # Default timezone, can be set via set_template_context
        self.include_metadata: bool = False  # Whether to wrap events in metadata
        self.template_metadata: dict[str, Any] | None = None  # Template metadata for wrapping
        self.generator_name: str | None = None  # Generator name for metadata

    def _substitute_env_vars(self, headers: dict[str, str]) -> dict[str, str]:
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

            pattern = r"\$\{([^}]+)\}"
            substituted[key] = re.sub(pattern, replace_var, value)

        return substituted

    @classmethod
    def from_config(
        cls,
        definition: OutputDefinition,
        retry_config: RetryConfig | None = None,
        buffer_size: int = 10000,
    ) -> "HTTPOutputHandler":
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

        handler = cls(
            name=definition.name,
            url=definition.url,
            method=definition.method or "POST",
            headers=definition.headers,
            batch_size=definition.batch_size or 100,
            batch_interval=definition.batch_interval or 5,
            timeout=definition.timeout or 30,
            retry_config=retry_config,
            buffer_size=buffer_size,
            streaming=definition.streaming if definition.streaming is not None else True,
            overflow_policy=definition.buffer_overflow_policy,
        )
        handler.include_metadata = definition.include_metadata or False
        return handler

    def initialize(self) -> None:
        """Initialize handler and start batch timer."""
        mode = "streaming" if self.streaming else "batching"
        logger.info(
            f"HTTP output '{self.name}' initialized: "
            f"URL={self.url}, method={self.method}, mode={mode}, "
            f"batch_size={self.batch_size}, batch_interval={self.batch_interval}s, "
            f"timeout={self.timeout}s"
        )
        # Start periodic batch flush timer (only for batching mode)
        if not self.streaming:
            self._start_batch_timer()

    def _start_batch_timer(self) -> None:
        """Start timer for periodic batch sends."""
        if self._batch_timer:
            self._batch_timer.cancel()

        self._batch_timer = threading.Timer(self.batch_interval, self._flush_batch_timer)
        self._batch_timer.daemon = True
        self._batch_timer.start()

    def _flush_batch_timer(self) -> None:
        """Flush batch when timer expires."""
        self._flush_batch_if_ready(force=True)
        # Restart timer
        self._start_batch_timer()

    def _enqueue_batch_buffer(self, event: str) -> None:
        """Put event on retry queue with explicit overflow policy."""
        try:
            self._batch_buffer.put_nowait(event)
            return
        except queue.Full:
            pass

        if self.overflow_policy == "drop_newest":
            with self._stats_lock:
                self._batch_buffer_dropped += 1
            logger.warning(
                f"HTTP output '{self.name}': Retry queue full ({self.buffer_size}), "
                f"dropping newest event (policy=drop_newest)"
            )
            return

        # drop_oldest: make room then enqueue
        try:
            self._batch_buffer.get_nowait()
        except queue.Empty:
            pass
        try:
            self._batch_buffer.put_nowait(event)
        except queue.Full:
            with self._stats_lock:
                self._batch_buffer_dropped += 1
            logger.warning(
                f"HTTP output '{self.name}': Retry queue full after eviction attempt, "
                f"dropping event (policy=drop_oldest)"
            )

    def _do_write(self, event: str) -> None:
        """Write event to batch buffer or send immediately if streaming.

        Args:
            event: Event string

        Note: Uses non-blocking queue operations to prevent deadlocks.
        """
        # If streaming, send immediately in background thread (non-blocking)
        if self.streaming:
            if self._executor:
                # Submit to thread pool - non-blocking
                self._executor.submit(self._send_single_event, event)
                # Errors are logged in _send_single_event, failures are buffered for retry
            else:
                # Fallback: send synchronously (blocks generator)
                try:
                    self._send_single_event(event)
                except Exception as e:
                    logger.debug(f"HTTP output '{self.name}': Failed to send event, buffering: {e}")
                    self._enqueue_batch_buffer(event)
            return

        # Non-blocking put - prevents deadlock from lock contention
        buffered_count = self._batch_buffer.qsize()

        # Log warning if buffer is getting full
        if buffered_count > self.buffer_size * 0.8:
            logger.warning(
                f"HTTP output '{self.name}': Buffer is {buffered_count}/{self.buffer_size} "
                f"({buffered_count/self.buffer_size*100:.1f}% full). "
                f"Consider increasing batch_size or checking connection status."
            )

        self._enqueue_batch_buffer(event)

        if self._batch_buffer.qsize() >= self.batch_size:
            self._flush_batch_if_ready(force=True)
        else:
            self._flush_batch_if_ready(force=False)

    def _flush_batch_if_ready(self, force: bool = False) -> None:
        """Flush batch if ready (size or interval).

        Args:
            force: Force flush even if conditions not met

        Note: Uses non-blocking queue operations to prevent deadlocks.
        """
        # Check queue size without blocking
        queue_size = self._batch_buffer.qsize()
        if queue_size == 0:
            return

        current_time = time.time()
        time_elapsed = current_time - self._last_batch_time >= self.batch_interval

        if force or queue_size >= self.batch_size or time_elapsed:
            # Drain queue (non-blocking)
            events_to_send = []
            try:
                while True:
                    try:
                        event = self._batch_buffer.get_nowait()
                        events_to_send.append(event)
                    except queue.Empty:
                        break

                if events_to_send:
                    self._last_batch_time = current_time

                    # Log periodic stats
                    self._log_periodic_stats()

                    # Send batch
                    # CRITICAL: Catch exceptions here to prevent dual buffering
                    # _send_batch() already re-buffers events on failure
                    # If we let exception propagate, base class will also buffer in self._buffer
                    try:
                        self._send_batch(events_to_send)
                    except Exception as e:
                        # _send_batch() already re-buffered events, so we just log
                        # Don't re-raise or base class will also buffer
                        logger.debug(
                            f"HTTP output '{self.name}': Batch send failed, events re-buffered: {e}"
                        )
            except Exception as e:
                logger.error(
                    f"HTTP output '{self.name}': Error draining batch buffer: {e}", exc_info=True
                )
                # Re-buffer events that were drained
                for event in events_to_send:
                    self._enqueue_batch_buffer(event)

    def _wrap_event_with_metadata(self, event: Any) -> dict[str, Any]:
        """Wrap event with logforge_metadata.

        Args:
            event: Event data (dict or string)

        Returns:
            Wrapped event with 'event' and 'logforge_metadata' fields
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Build metadata
        metadata = {
            "generated_at": datetime.now(ZoneInfo(self.timezone)).isoformat(),
        }

        # Add generator name
        if self.generator_name:
            metadata["generator"] = self.generator_name

        # Add template information from metadata
        if self.template_metadata:
            if "template_id" in self.template_metadata:
                metadata["template_id"] = self.template_metadata["template_id"]
            if "vendor" in self.template_metadata:
                metadata["vendor"] = self.template_metadata["vendor"]
            if "product" in self.template_metadata:
                metadata["product"] = self.template_metadata["product"]
            if "data_source" in self.template_metadata:
                metadata["data_source"] = self.template_metadata["data_source"]

        return {"event": event, "logforge_metadata": metadata}

    def _sanitize_header_value(self, key: str, value: str) -> str:
        """Sanitize sensitive header values for logging.

        Args:
            key: Header key
            value: Header value

        Returns:
            Sanitized value
        """
        key_lower = key.lower()
        if key_lower in ("authorization", "x-api-key", "x-auth-token"):
            # Redact tokens but keep prefix
            if value.startswith("Bearer "):
                return "Bearer ***"
            elif value.startswith("Splunk "):
                return "Splunk ***"
            elif value.startswith("Basic "):
                return "Basic ***"
            else:
                return "***"
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
        return body[:max_length] + "..."

    def _send_single_event(self, event: str) -> None:
        """Send single event immediately via HTTP.

        Args:
            event: Event string

        Raises:
            Exception: On send failure
        """
        start_time = time.time()

        try:
            logger.debug(f"HTTP output '{self.name}': Sending single event to {self.url}")

            # Parse event as JSON (if it's a JSON string)
            try:
                json_event = json.loads(event)
            except (json.JSONDecodeError, TypeError):
                # Not JSON, send as string
                json_event = event

            # Wrap event with metadata if enabled
            if self.include_metadata:
                payload = self._wrap_event_with_metadata(json_event)
            else:
                payload = json_event

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
                bytes_sent = len(response.content) if hasattr(response, "content") else 0

                with self._stats_lock:
                    self._events_sent += 1
                    self._batches_sent += 1  # Count as batch for stats
                    self._total_bytes_sent += bytes_sent
                    self._last_success_time = time.time()
                    # Keep last 100 response times
                    self._response_times.append(response_time)
                    if len(self._response_times) > 100:
                        self._response_times.pop(0)

                logger.debug(
                    f"HTTP output '{self.name}': Successfully sent event "
                    f"(status={response.status_code}, latency={response_time:.1f}ms)"
                )

            except requests.HTTPError:
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
                    self._events_failed += 1
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

                # Buffer for retry
                self._enqueue_batch_buffer(event)

                raise

        except requests.exceptions.Timeout:
            # Timeout error
            response_time = (time.time() - start_time) * 1000
            error_msg = f"Request timeout after {self.timeout}s"

            with self._stats_lock:
                self._events_failed += 1
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = error_msg
                self._last_error_type = "TIMEOUT"
                self._timeout_errors += 1

            logger.error(f"HTTP output '{self.name}': Request timeout after {self.timeout}s")

            # Buffer for retry
            self._enqueue_batch_buffer(event)

            raise

        except requests.exceptions.ConnectionError as e:
            # Connection error
            error_msg = str(e)

            with self._stats_lock:
                self._events_failed += 1
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"Connection failed: {error_msg}"
                self._last_error_type = "CONNECTION_ERROR"
                self._connection_errors += 1

            logger.error(
                f"HTTP output '{self.name}': Connection failed: {type(e).__name__} - "
                f"{error_msg}"
            )

            # Buffer for retry
            self._enqueue_batch_buffer(event)

            raise

        except requests.exceptions.RequestException as e:
            # Other request exceptions
            error_type = type(e).__name__
            error_msg = str(e)

            with self._stats_lock:
                self._events_failed += 1
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"{error_type}: {error_msg}"
                self._last_error_type = error_type
                self._connection_errors += 1

            logger.error(f"HTTP output '{self.name}': Request failed: {error_type} - {error_msg}")

            # Buffer for retry
            self._enqueue_batch_buffer(event)

            raise

        except Exception as e:
            # Unexpected errors
            error_type = type(e).__name__
            error_msg = str(e)

            with self._stats_lock:
                self._events_failed += 1
                self._batches_failed += 1
                self._last_failure_time = time.time()
                self._last_error_message = f"{error_type}: {error_msg}"
                self._last_error_type = error_type

            logger.error(
                f"HTTP output '{self.name}': Unexpected error sending event: {error_type} - {error_msg}",
                exc_info=True,
            )

            # Buffer for retry
            self._enqueue_batch_buffer(event)

            raise

    def _send_batch(self, events: list[str]) -> None:
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

            # Wrap events with metadata if enabled
            if self.include_metadata:
                wrapped_events = []
                for event in json_events:
                    wrapped = self._wrap_event_with_metadata(event)
                    wrapped_events.append(wrapped)

                # Always send as array for batches
                payload = wrapped_events
            else:
                # Always send as array for batches
                payload = json_events

            # Log request details at DEBUG level
            if logger.isEnabledFor(10):  # DEBUG level
                sanitized_headers = {
                    k: self._sanitize_header_value(k, v)
                    for k, v in self._substituted_headers.items()
                }
                logger.debug(f"HTTP output '{self.name}': Request headers: {sanitized_headers}")

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
                bytes_sent = len(response.content) if hasattr(response, "content") else 0

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

            except requests.HTTPError:
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

                # Re-buffer events for retry (non-blocking)
                for event in events:
                    self._enqueue_batch_buffer(event)

                raise

        except requests.exceptions.Timeout:
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

            # Re-buffer events for retry (non-blocking)
            for event in events:
                self._enqueue_batch_buffer(event)

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

            # Re-buffer events for retry (non-blocking)
            for event in events:
                self._enqueue_batch_buffer(event)

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

            # Re-buffer events for retry (non-blocking)
            for event in events:
                self._enqueue_batch_buffer(event)

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
                exc_info=True,
            )

            # Re-buffer events for retry (non-blocking)
            for event in events:
                self._enqueue_batch_buffer(event)

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
            except Exception:
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

    def write_batch(self, events: list[str]) -> None:
        """Write batch of events.

        Args:
            events: List of event strings
        """
        for event in events:
            self.write(event)

    def get_statistics(self) -> dict:
        """Get output handler statistics.

        Returns:
            Dictionary with statistics and health information (includes base backlog/dropped/healthy).
        """
        base_stats = super().get_statistics()
        # Get buffered count (queue is thread-safe, no lock needed)
        buffered_count = self._batch_buffer.qsize()
        base_stats["backlog_size"] = base_stats["backlog_size"] + buffered_count

        # Get stats data (avoid nested locks)
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

            # Copy all stats values (read-only, no need to hold lock during dict creation)
            events_sent = self._events_sent
            events_failed = self._events_failed
            batches_sent = self._batches_sent
            batches_failed = self._batches_failed
            connection_errors = self._connection_errors
            http_errors = self._http_errors
            timeout_errors = self._timeout_errors
            auth_errors = self._auth_errors
            total_bytes_sent = self._total_bytes_sent
            last_success_time = self._last_success_time
            last_failure_time = self._last_failure_time
            last_error_message = self._last_error_message
            last_error_type = self._last_error_type
            batch_buffer_dropped = self._batch_buffer_dropped

        # Build stats dict outside of locks (all values are now copied); merge with base
        stats = {
            **base_stats,
            "handler_name": self.name,
            "handler_type": "http",
            "url": self.url,
            "health_status": health_status,
            "events_sent": events_sent,
            "events_failed": events_failed,
            "batches_sent": batches_sent,
            "batches_failed": batches_failed,
            "buffered_events": buffered_count,
            "batch_buffer_dropped": batch_buffer_dropped,
            "connection_errors": connection_errors,
            "http_errors": http_errors,
            "timeout_errors": timeout_errors,
            "auth_errors": auth_errors,
            "total_bytes_sent": total_bytes_sent,
            "average_response_time_ms": round(avg_response_time, 2) if avg_response_time else None,
            "last_success_time": (
                datetime.fromtimestamp(last_success_time, ZoneInfo(self.timezone)).isoformat()
                if last_success_time
                else None
            ),
            "last_failure_time": (
                datetime.fromtimestamp(last_failure_time, ZoneInfo(self.timezone)).isoformat()
                if last_failure_time
                else None
            ),
            "last_error_message": last_error_message,
            "last_error_type": last_error_type,
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

    def set_template_context(
        self,
        generator_name: str,
        output_name: str,
        template_metadata: dict[str, Any] | None = None,
        organization_name: str | None = None,
        timezone: str | None = None,
    ) -> None:
        """Set template context (including timezone) for HTTP handler.

        Args:
            generator_name: Generator name
            output_name: Output handler name (unused for HTTP)
            template_metadata: Template metadata dict (vendor, product, data_source, template_id)
            organization_name: Organization name (unused for HTTP)
            timezone: Timezone string (e.g., 'America/New_York'). Updates handler timezone.
        """
        if timezone:
            self.timezone = timezone
        if template_metadata:
            self.template_metadata = template_metadata.copy()
        self.generator_name = generator_name

    def close(self) -> None:
        """Close handler and flush remaining batches."""
        # Log final statistics
        stats = self.get_statistics()
        logger.info(
            f"HTTP output '{self.name}' closing: "
            f"sent={stats['events_sent']} events, "
            f"failed={stats['events_failed']} events, "
            f"buffered={stats['buffered_events']} events remaining, "
            f"batch_buffer_dropped={stats.get('batch_buffer_dropped', 0)}"
        )

        # Cancel timer
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None

        # Stop async HTTP workers before touching shared retry queue
        if self._executor:
            logger.debug(f"HTTP output '{self.name}': Shutting down thread pool executor")
            try:
                self._executor.shutdown(wait=True, timeout=30)
            except TypeError:
                self._executor.shutdown(wait=True)
            self._executor = None

        # Flush any remaining events
        self._flush_batch_if_ready(force=True)

        remaining = self._batch_buffer.qsize()
        if remaining:
            logger.warning(
                f"HTTP output '{self.name}': {remaining} event(s) still in retry queue after close flush"
            )
