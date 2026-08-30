"""Internal log generator - forwards application logs to configured outputs."""

import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from meltr.core.generator import GeneratorState
from meltr.outputs.base import OutputHandler
from meltr.utils.logging import InternalLogForwardingHandler, get_logger

logger = get_logger(__name__)

INTERNAL_LOGS_GENERATOR_NAME = "internal-logs"
QUEUE_GET_TIMEOUT = 1.0
INTERNAL_LOG_QUEUE_MAXSIZE = 10000


class InternalLogGenerator:
    """Forwards application log records from a queue to output handlers.

    Uses the same lifecycle and status interface as Generator so it appears
    in generators list and API. Does not use a template.
    """

    def __init__(self, output_handlers: list[OutputHandler]) -> None:
        self.name = INTERNAL_LOGS_GENERATOR_NAME
        self.output_handlers = output_handlers
        self._queue: queue.Queue[str] = queue.Queue(maxsize=INTERNAL_LOG_QUEUE_MAXSIZE)
        self._handler: InternalLogForwardingHandler | None = None
        self._state = GeneratorState.STOPPED
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._events_forwarded = 0
        self._errors = 0
        self._last_event_time: float | None = None
        self._start_time: float | None = None
        self._stats_lock = threading.Lock()

    @property
    def state(self) -> GeneratorState:
        with self._state_lock:
            return self._state

    def _transition_to(self, new_state: GeneratorState) -> None:
        with self._state_lock:
            self._state = new_state

    def start(self) -> None:
        if self._state != GeneratorState.STOPPED:
            return
        self._transition_to(GeneratorState.STARTING)
        self._handler = InternalLogForwardingHandler(
            self._queue, max_queue_size=INTERNAL_LOG_QUEUE_MAXSIZE
        )
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        meltr_logger = logging.getLogger("meltr")
        meltr_logger.addHandler(self._handler)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._start_time = time.time()
        self._transition_to(GeneratorState.RUNNING)
        logger.info(
            f"Internal log generator started, forwarding to {len(self.output_handlers)} output(s)"
        )

    def stop(self) -> None:
        if self._state in (GeneratorState.STOPPED, GeneratorState.STOPPING):
            return
        self._transition_to(GeneratorState.STOPPING)
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._handler:
            try:
                meltr_logger = logging.getLogger("meltr")
                meltr_logger.removeHandler(self._handler)
            except Exception as e:
                logger.warning(f"Error removing internal log handler: {e}")
            self._handler = None
        for h in self.output_handlers:
            try:
                h.close()
            except Exception as e:
                logger.debug(f"Error closing output handler {h.name}: {e}")
        self._transition_to(GeneratorState.STOPPED)
        logger.info("Internal log generator stopped")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                try:
                    line = self._queue.get(timeout=QUEUE_GET_TIMEOUT)
                except queue.Empty:
                    continue
                self._write_to_outputs(line)
                with self._stats_lock:
                    self._events_forwarded += 1
                    self._last_event_time = time.time()
            except Exception as e:
                with self._stats_lock:
                    self._errors += 1
                logger.debug(f"Internal log generator write error: {e}")
        logger.debug("Internal log generator loop exited")

    def _write_to_outputs(self, event: str) -> None:
        for h in self.output_handlers:
            try:
                h.write(event)
            except Exception as e:
                logger.warning(f"Internal log output {getattr(h, 'name', '?')} write failed: {e}")

    def get_statistics(self) -> dict[str, Any]:
        with self._stats_lock:
            uptime = 0
            if self._start_time:
                uptime = int(time.time() - self._start_time)
            return {
                "events_generated": self._events_forwarded,
                "errors": self._errors,
                "uptime": uptime,
                "last_event": (
                    datetime.fromtimestamp(self._last_event_time, ZoneInfo("UTC")).isoformat()
                    if self._last_event_time
                    else None
                ),
                "last_error": None,
            }

    def get_status(self) -> dict[str, Any]:
        output_stats = []
        for h in self.output_handlers:
            if hasattr(h, "get_statistics"):
                try:
                    output_stats.append(h.get_statistics())
                except Exception:
                    output_stats.append(
                        {
                            "handler_name": getattr(h, "name", "unknown"),
                            "handler_type": type(h).__name__,
                            "health_status": "healthy" if h.is_healthy() else "degraded",
                        }
                    )
            else:
                output_stats.append(
                    {
                        "handler_name": getattr(h, "name", "unknown"),
                        "handler_type": type(h).__name__,
                        "health_status": "healthy" if h.is_healthy() else "degraded",
                    }
                )
        return {
            "name": self.name,
            "state": self.state.value,
            "template": "_internal",
            "enabled": True,
            "timezone": None,
            "frequency": {"base_rate": 0.0, "current_rate": 0.0, "source": "internal_logs"},
            "outputs": [getattr(h, "name", "?") for h in self.output_handlers],
            "output_status": output_stats,
            "statistics": self.get_statistics(),
        }
