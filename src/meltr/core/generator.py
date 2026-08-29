"""Generator class with state machine and lifecycle management."""

import threading
import time
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from meltr.core.pipeline import ScheduleSharedState
from zoneinfo import ZoneInfo

from meltr.core.config import GeneratorConfig
from meltr.entities.registry import EntityRegistry
from meltr.outputs.base import OutputHandler
from meltr.templates.loader import TemplateLoader
from meltr.templates.renderer import TemplateRenderer
from meltr.utils.logging import get_logger
from meltr.utils.public_errors import sanitize_stored_error

logger = get_logger(__name__)


class GeneratorState(Enum):
    """Generator state enumeration."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    STOPPING = "STOPPING"


# Valid state transitions
VALID_TRANSITIONS: dict[GeneratorState, list[GeneratorState]] = {
    GeneratorState.STOPPED: [GeneratorState.STARTING],
    GeneratorState.STARTING: [GeneratorState.RUNNING, GeneratorState.ERROR, GeneratorState.STOPPED],
    GeneratorState.RUNNING: [
        GeneratorState.STOPPING,
        GeneratorState.DEGRADED,
        GeneratorState.ERROR,
    ],
    GeneratorState.DEGRADED: [
        GeneratorState.RUNNING,
        GeneratorState.ERROR,
        GeneratorState.STOPPING,
    ],
    GeneratorState.ERROR: [GeneratorState.STARTING, GeneratorState.STOPPED],
    GeneratorState.STOPPING: [GeneratorState.STOPPED, GeneratorState.ERROR],
}


class Generator:
    """Manages event generation lifecycle for a single generator."""

    def __init__(
        self,
        name: str,
        config: GeneratorConfig,
        template_loader: TemplateLoader,
        registry: EntityRegistry,
        output_handlers: list[OutputHandler],
        schedule_state: "ScheduleSharedState | None" = None,
    ) -> None:
        """Initialize generator.

        Args:
            name: Generator name
            config: Generator configuration
            template_loader: Template loader instance
            registry: Entity registry instance
            output_handlers: List of output handlers
        """
        self.name = name
        self.config = config
        self.template_loader = template_loader
        self.registry = registry
        self.output_handlers = output_handlers
        self._schedule_state = schedule_state
        self._schedule_started_at: datetime | None = None
        self._schedule_events_emitted = 0

        # State management
        self._state = GeneratorState.STOPPED
        self._state_lock = threading.Lock()

        # Generation control
        self._stop_event = threading.Event()

        # Statistics
        self._events_generated = 0
        self._errors = 0
        self._start_time: float | None = None
        self._last_event_time: float | None = None
        self._last_error: str | None = None
        self._stats_lock = threading.Lock()

        # Template renderer
        self._renderer: TemplateRenderer | None = None
        self._template_content: str | None = None
        self._template_info: Any | None = None  # TemplateInfo object

    @property
    def state(self) -> GeneratorState:
        """Get current generator state."""
        with self._state_lock:
            return self._state

    def get_timezone(self) -> str:
        """Get timezone for this generator.

        Returns:
            Timezone string (e.g., 'America/New_York'). Uses generator config
            timezone if set, otherwise falls back to organization timezone.
        """
        if self.config.timezone:
            return self.config.timezone
        return self.registry.get_organization_timezone()

    def _transition_to(self, new_state: GeneratorState) -> bool:
        """Transition to new state if valid.

        Args:
            new_state: Target state

        Returns:
            True if transition successful, False otherwise
        """
        with self._state_lock:
            current_state = self._state

            if new_state not in VALID_TRANSITIONS.get(current_state, []):
                logger.warning(
                    f"Generator {self.name}: Invalid state transition {current_state} -> {new_state}"
                )
                return False

            old_state = self._state
            self._state = new_state
            logger.info(f"Generator {self.name}: {old_state.value} -> {new_state.value}")
            return True

    def start(self) -> None:
        """Start event generation."""
        if not self._transition_to(GeneratorState.STARTING):
            raise RuntimeError(f"Generator {self.name} cannot start from {self.state.value} state")

        try:
            # Validate entities are available (strict validation)
            self._validate_entities_available()

            # Load template
            template_info = self.template_loader.resolve_template(self.config.template)
            if not template_info:
                raise ValueError(f"Template not found: {self.config.template}")

            self._template_info = template_info

            # Load template content
            with template_info.template_path.open("r", encoding="utf-8") as f:
                self._template_content = f.read()

            # Get timezone for context (generator config takes precedence)
            timezone = self.get_timezone()

            # Create renderer with timezone
            self._renderer = TemplateRenderer(self.registry, timezone=timezone)

            # Initialize output handlers with template context
            for handler in self.output_handlers:
                try:
                    # Pass template context to file output handlers
                    if hasattr(handler, "set_template_context"):
                        template_metadata = {
                            "vendor": template_info.vendor,
                            "product": template_info.product,
                            "data_source": template_info.data_source,
                            "template_id": template_info.id,  # Full template ID for metadata wrapping
                        }
                        # Note: collection is not part of the template ID structure
                        # Template ID format: vendor/product/data_source/template_name
                        # If collection is needed, it would need to be added to metadata

                        organization_name = None
                        try:
                            org = self.registry.get_organization()
                            if org and "name" in org:
                                organization_name = org["name"]
                        except Exception:
                            pass  # Organization not available

                        # Set template context on all handlers that support it
                        if hasattr(handler, "set_template_context"):
                            handler.set_template_context(
                                generator_name=self.name,
                                output_name=handler.name,
                                template_metadata=template_metadata,
                                organization_name=organization_name,
                                timezone=timezone,
                            )

                    # Output handlers should have an initialize method if needed
                    if hasattr(handler, "initialize"):
                        handler.initialize()
                except Exception as e:
                    logger.error(f"Generator {self.name}: Failed to initialize output handler: {e}")
                    raise

            if self.config.schedule and self._schedule_state is None:
                self._schedule_started_at = datetime.now(ZoneInfo(self.get_timezone()))
                self._schedule_events_emitted = 0

            # Clear stop event (generation loop will be started by engine)
            logger.info(
                f"Generator {self.name}: Clearing stop_event (was set={self._stop_event.is_set()})"
            )
            self._stop_event.clear()
            logger.info(
                f"Generator {self.name}: stop_event cleared, is_set={self._stop_event.is_set()}"
            )

            # Transition to RUNNING after successful initialization
            if self._transition_to(GeneratorState.RUNNING):
                self._start_time = time.time()
                logger.info(
                    f"Generator {self.name} initialized and ready (stop_event={self._stop_event.is_set()})"
                )
            else:
                raise RuntimeError("Failed to transition to RUNNING state")

        except Exception as e:
            logger.error(f"Generator {self.name}: Failed to start: {e}", exc_info=True)
            self._last_error = str(e)
            self._transition_to(GeneratorState.ERROR)
            raise

    def stop(self) -> None:
        """Stop event generation gracefully."""
        if self.state in (GeneratorState.STOPPED, GeneratorState.STOPPING):
            return

        if not self._transition_to(GeneratorState.STOPPING):
            logger.warning(f"Generator {self.name}: Cannot stop from {self.state.value} state")
            return

        # Signal stop
        self._stop_event.set()

        # Note: Thread pool will handle thread lifecycle
        # The future will complete when _generate_loop exits

        # Close output handlers
        for handler in self.output_handlers:
            try:
                handler.close()
            except Exception as e:
                logger.error(f"Generator {self.name}: Error closing output handler: {e}")

        self._transition_to(GeneratorState.STOPPED)
        logger.info(f"Generator {self.name} stopped")

    def _generate_loop(self) -> None:
        """Main generation loop."""
        logger.info(f"Generator {self.name}: Loop thread started!")
        logger.info(f"Generator {self.name}: Stop event is_set={self._stop_event.is_set()}")
        try:
            iteration = 0
            while not self._stop_event.is_set():
                iteration += 1
                logger.info(
                    f"Generator {self.name}: Loop iteration {iteration} (stop_event={self._stop_event.is_set()})"
                )

                # Calculate current rate from template metadata
                logger.debug(f"Generator {self.name}: Calculating rate from template metadata...")
                if not self._template_info or not self._template_info.metadata:
                    logger.error(f"Generator {self.name}: Template metadata not available")
                    rate = 0.0
                else:
                    from meltr.core.frequency import calculate_rate_from_template_metadata

                    timezone = self.get_timezone()
                    rate = calculate_rate_from_template_metadata(
                        self._template_info.metadata, timezone
                    )
                logger.info(f"Generator {self.name}: Calculated rate: {rate} events/sec")

                if rate <= 0:
                    # Sleep and continue if rate is 0 (interruptible)
                    logger.info(f"Generator {self.name}: Rate is 0 or negative, sleeping 1.0s")
                    if self._stop_event.wait(timeout=1.0):
                        # Stop event was set during sleep
                        logger.info(f"Generator {self.name}: Stop requested during sleep")
                        break
                    continue

                schedule_decision = self._evaluate_schedule_gate()
                if schedule_decision is not None:
                    if not schedule_decision.emit:
                        if schedule_decision.reason == "burst_complete":
                            logger.info(f"Generator {self.name}: Burst schedule complete, stopping")
                            self._stop_event.set()
                            break
                        logger.debug(
                            f"Generator {self.name}: Schedule gate blocked emit ({schedule_decision.reason})"
                        )
                        if self._stop_event.wait(timeout=1.0):
                            break
                        continue

                # Calculate sleep interval (events per second)
                sleep_interval = 1.0 / rate
                logger.info(
                    f"Generator {self.name}: About to generate event, will sleep {sleep_interval:.3f}s after"
                )

                # Generate event
                try:
                    logger.debug(f"Generator {self.name}: Calling _render_event()...")
                    event = self._render_event()
                    logger.info(
                        f"Generator {self.name}: Event generated ({len(event)} chars)"
                        if event
                        else "Generator {self.name}: Event generation returned None"
                    )

                    if event:
                        logger.debug(
                            f"Generator {self.name}: Writing event to {len(self.output_handlers)} output handler(s)..."
                        )
                        self._write_to_outputs(event)
                        logger.debug(f"Generator {self.name}: Event written successfully")

                        with self._stats_lock:
                            self._events_generated += 1
                            self._last_event_time = time.time()
                            logger.info(
                                f"Generator {self.name}: Event #{self._events_generated} generated successfully"
                            )
                        self._record_schedule_emit()
                    else:
                        logger.warning(
                            f"Generator {self.name}: _render_event() returned None, skipping output"
                        )

                except Exception as e:
                    logger.error(
                        f"Generator {self.name}: Error generating event: {e}", exc_info=True
                    )
                    with self._stats_lock:
                        self._errors += 1
                        self._last_error = str(e)

                    # Check if error should transition to ERROR state
                    # (template errors = ERROR, output errors = DEGRADED)
                    if "template" in str(e).lower() or "render" in str(e).lower():
                        logger.error(
                            f"Generator {self.name}: Template/render error, transitioning to ERROR state"
                        )
                        self._transition_to(GeneratorState.ERROR)
                        break
                    else:
                        # Output error - transition to DEGRADED
                        if self.state == GeneratorState.RUNNING:
                            logger.warning(
                                f"Generator {self.name}: Output error, transitioning to DEGRADED state"
                            )
                            self._transition_to(GeneratorState.DEGRADED)

                # Sleep to maintain rate (interruptible and respects variable frequency)
                # For long intervals (>60s), break into chunks to allow rate recalculation
                # This ensures time-based frequency changes (business hours, etc.) are detected quickly
                max_sleep_chunk = 60.0  # Maximum sleep chunk in seconds
                remaining_sleep = sleep_interval

                logger.debug(
                    f"Generator {self.name}: Sleeping {sleep_interval:.3f}s before next iteration"
                )

                while remaining_sleep > 0 and not self._stop_event.is_set():
                    # Sleep in chunks to allow rate recalculation for variable frequency
                    chunk = min(remaining_sleep, max_sleep_chunk)

                    if self._stop_event.wait(timeout=chunk):
                        # Stop event was set during sleep
                        logger.info(f"Generator {self.name}: Stop requested during sleep")
                        break

                    remaining_sleep -= chunk

                    # If we have more sleep remaining, recalculate rate to catch time-based changes
                    # (e.g., business hours starting, weekend transitions, etc.)
                    if remaining_sleep > 0:
                        # Recalculate rate to detect time-based frequency changes
                        if self._template_info and self._template_info.metadata:
                            from meltr.core.frequency import calculate_rate_from_template_metadata

                            new_rate = calculate_rate_from_template_metadata(
                                self._template_info.metadata, self.get_timezone()
                            )

                            # If rate changed significantly, recalculate remaining sleep
                            # This handles transitions like business hours starting
                            if abs(new_rate - rate) > (rate * 0.1):  # 10% change threshold
                                logger.debug(
                                    f"Generator {self.name}: Rate changed from {rate:.6f} to {new_rate:.6f} "
                                    f"during sleep, recalculating remaining interval"
                                )
                                # Recalculate remaining sleep based on new rate
                                new_sleep_interval = (
                                    1.0 / new_rate if new_rate > 0 else remaining_sleep
                                )
                                remaining_sleep = min(remaining_sleep, new_sleep_interval)
                                rate = new_rate

                if self._stop_event.is_set():
                    logger.info(f"Generator {self.name}: Stop requested during sleep")
                    break

                logger.debug(f"Generator {self.name}: Sleep completed, starting next iteration")

            logger.info(
                f"Generator {self.name}: Loop exited - stop_event is_set={self._stop_event.is_set()}"
            )

        except Exception as e:
            logger.error(f"Generator {self.name}: Generation loop error: {e}", exc_info=True)
            self._transition_to(GeneratorState.ERROR)

    def _evaluate_schedule_gate(self):
        """Evaluate schedule gate when configured."""
        if not self.config.schedule:
            return None

        from meltr.core.schedule import evaluate_schedule

        tz = ZoneInfo(self.get_timezone())
        now = datetime.now(tz)
        if self._schedule_state is not None:
            started_at = self._schedule_state.started_at.astimezone(tz)
            events_emitted = self._schedule_state.events_emitted
        else:
            started_at = self._schedule_started_at or now
            events_emitted = self._schedule_events_emitted

        return evaluate_schedule(
            self.config.schedule,
            now=now,
            events_emitted=events_emitted,
            started_at=started_at,
        )

    def _record_schedule_emit(self) -> None:
        """Increment schedule counters after a successful emit."""
        if not self.config.schedule:
            return
        if self._schedule_state is not None:
            self._schedule_state.increment()
        else:
            self._schedule_events_emitted += 1

    def _render_event(self) -> str | None:
        """Render a single event from template.

        Returns:
            Rendered event string or None on error
        """
        logger.debug(f"Generator {self.name}: _render_event() called")

        if not self._renderer or not self._template_content:
            logger.error(
                f"Generator {self.name}: Renderer or template not initialized - renderer={self._renderer is not None}, template_content={self._template_content is not None}"
            )
            raise RuntimeError("Renderer or template not initialized")

        logger.debug(f"Generator {self.name}: Calling renderer.render_string()...")
        try:
            event = self._renderer.render_string(self._template_content)
            logger.debug(
                f"Generator {self.name}: render_string() completed, returned {len(event) if event else 0} chars"
            )
            return event
        except Exception as e:
            logger.error(
                f"Generator {self.name}: render_string() raised exception: {e}", exc_info=True
            )
            raise

    def _write_to_outputs(self, event: str) -> None:
        """Write event to all output handlers.

        Args:
            event: Event string to write
        """
        logger.debug(
            f"Generator {self.name}: _write_to_outputs() called with {len(self.output_handlers)} handler(s)"
        )

        success_count = 0
        for i, handler in enumerate(self.output_handlers):
            handler_name = getattr(handler, "name", f"handler_{i}")
            logger.debug(
                f"Generator {self.name}: Writing to output handler {i+1}/{len(self.output_handlers)}: {handler_name}"
            )
            try:
                handler.write(event)
                success_count += 1
                logger.debug(f"Generator {self.name}: Successfully wrote to handler {handler_name}")
            except Exception as e:
                logger.warning(
                    f"Generator {self.name}: Output handler {handler_name} write failed: {e}",
                    exc_info=True,
                )
                # Don't raise - let other handlers try
                # State will transition to DEGRADED if all handlers fail

        if success_count == 0:
            if self.state == GeneratorState.RUNNING:
                self._transition_to(GeneratorState.DEGRADED)
        elif self.state == GeneratorState.DEGRADED:
            self._transition_to(GeneratorState.RUNNING)

        logger.debug(f"Generator {self.name}: _write_to_outputs() completed")

    def _validate_entities_available(self) -> None:
        """Validate that entities are available for generation.

        Raises:
            ValueError: If entities are missing or invalid
        """
        if not self.registry._data:
            raise ValueError("Entity registry is empty. Add entities before starting generators.")

        users = self.registry._data.get("users", [])
        devices = self.registry._data.get("devices", [])
        services = self.registry._data.get("services", [])

        if len(users) == 0:
            raise ValueError(
                "At least one user is required to start generators. Import entities first."
            )
        if len(devices) == 0:
            raise ValueError(
                "At least one device is required to start generators. Import entities first."
            )
        if len(services) == 0:
            raise ValueError(
                "At least one service is required to start generators. Import entities first."
            )

    def get_statistics(self) -> dict:
        """Get generator statistics.

        Returns:
            Dictionary with statistics
        """
        with self._stats_lock:
            uptime = 0
            if self._start_time:
                uptime = int(time.time() - self._start_time)

            return {
                "events_generated": self._events_generated,
                "errors": self._errors,
                "uptime": uptime,
                "last_event": (
                    datetime.fromtimestamp(
                        self._last_event_time, ZoneInfo(self.get_timezone())
                    ).isoformat()
                    if self._last_event_time
                    else None
                ),
                "last_error": sanitize_stored_error(self._last_error),
            }

    def get_status(self) -> dict:
        """Get generator status with full details.

        Returns:
            Dictionary with status information
        """
        stats = self.get_statistics()
        # Calculate current rate from template metadata
        if (
            self.state == GeneratorState.RUNNING
            and self._template_info
            and self._template_info.metadata
        ):
            from meltr.core.frequency import calculate_rate_from_template_metadata

            timezone = self.get_timezone()
            current_rate = calculate_rate_from_template_metadata(
                self._template_info.metadata, timezone
            )
        else:
            current_rate = 0.0

        # Get output handler statistics
        output_stats = []
        for handler in self.output_handlers:
            if hasattr(handler, "get_statistics"):
                try:
                    output_stats.append(handler.get_statistics())
                except Exception as e:
                    logger.warning(
                        f"Generator {self.name}: Failed to get statistics for output {handler.name}: {e}"
                    )
                    # Fallback to basic info
                    output_stats.append(
                        {
                            "handler_name": handler.name if hasattr(handler, "name") else "unknown",
                            "handler_type": type(handler).__name__,
                            "health_status": "unknown",
                        }
                    )
            else:
                # Handler doesn't support statistics, provide basic info
                output_stats.append(
                    {
                        "handler_name": handler.name if hasattr(handler, "name") else "unknown",
                        "handler_type": type(handler).__name__,
                        "health_status": "healthy" if handler.is_healthy() else "degraded",
                    }
                )

        return {
            "name": self.name,
            "state": self.state.value,
            "template": self.config.template,
            "enabled": self.config.enabled,
            "timezone": self.config.timezone,  # Include timezone in status
            "frequency": {
                "base_rate": (
                    self._template_info.metadata.base_frequency / 3600.0
                    if (
                        self._template_info
                        and self._template_info.metadata
                        and self._template_info.metadata.base_frequency
                    )
                    else 0.0
                ),
                "current_rate": current_rate,
                "source": "template_metadata",
            },
            "outputs": [
                handler.name for handler in self.output_handlers if hasattr(handler, "name")
            ],
            "output_status": output_stats,
            "statistics": stats,
        }
