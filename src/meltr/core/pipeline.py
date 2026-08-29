"""Multi-template pipeline orchestrator."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from meltr.core.config import GeneratorConfig, PipelineConfig
from meltr.core.generator import Generator, GeneratorState
from meltr.outputs.factory import create_output_handlers
from meltr.templates.loader import TemplateLoader
from meltr.utils.logging import get_logger

if TYPE_CHECKING:
    from meltr.entities.registry import EntityRegistry
    from meltr.templates.cache import TemplateCache

logger = get_logger(__name__)


class ScheduleSharedState:
    """Thread-safe schedule counters shared by pipeline child generators."""

    def __init__(self, started_at: datetime) -> None:
        self.started_at = started_at
        self._events_emitted = 0
        self._lock = threading.Lock()

    @property
    def events_emitted(self) -> int:
        with self._lock:
            return self._events_emitted

    def increment(self) -> None:
        with self._lock:
            self._events_emitted += 1

    def reset(self) -> None:
        with self._lock:
            self._events_emitted = 0
            self.started_at = datetime.now(timezone.utc)


class Pipeline:
    """Orchestrates child generators that share outputs and schedule."""

    def __init__(
        self,
        config: PipelineConfig,
        generators: list[Generator],
        child_generator_names: list[str],
        schedule_state: ScheduleSharedState,
    ) -> None:
        self.config = config
        self.generators = generators
        self.child_generator_names = child_generator_names
        self.schedule_state = schedule_state

    @staticmethod
    def child_generator_name(pipeline_name: str, index: int) -> str:
        return f"{pipeline_name}::{index}"

    @classmethod
    def create(
        cls,
        config: PipelineConfig,
        *,
        template_cache: TemplateCache,
        template_loader: TemplateLoader,
        registry: EntityRegistry,
        output_definitions,
        retry_config,
        buffer_size: int,
    ) -> Pipeline:
        """Build a pipeline and its child generators."""
        schedule_state = ScheduleSharedState(datetime.now(timezone.utc))

        generators: list[Generator] = []
        child_names: list[str] = []

        for index, stream in enumerate(config.streams):
            template_info = template_cache.get_template(stream.template)
            if not template_info:
                raise ValueError(f"Template not found: {stream.template}")

            child_name = cls.child_generator_name(config.name, index)
            gen_config = GeneratorConfig(
                name=child_name,
                template=stream.template,
                enabled=False,
                outputs=list(config.outputs),
                timezone=config.timezone,
                schedule=config.schedule,
            )
            child_output_handlers = create_output_handlers(
                config.outputs,
                output_definitions,
                retry_config=retry_config,
                buffer_size=buffer_size,
            )
            generator = Generator(
                name=child_name,
                config=gen_config,
                template_loader=template_loader,
                registry=registry,
                output_handlers=child_output_handlers,
                schedule_state=schedule_state,
            )
            generators.append(generator)
            child_names.append(child_name)

        return cls(config, generators, child_names, schedule_state)

    def reset_schedule(self) -> None:
        """Reset shared schedule counters when the pipeline starts."""
        self.schedule_state.reset()

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def state(self) -> GeneratorState:
        states = [gen.state for gen in self.generators]
        if not states:
            return GeneratorState.STOPPED
        if any(state == GeneratorState.ERROR for state in states):
            return GeneratorState.ERROR
        if any(state == GeneratorState.RUNNING for state in states):
            return GeneratorState.RUNNING
        if any(state == GeneratorState.STARTING for state in states):
            return GeneratorState.STARTING
        if any(state == GeneratorState.STOPPING for state in states):
            return GeneratorState.STOPPING
        if any(state == GeneratorState.DEGRADED for state in states):
            return GeneratorState.DEGRADED
        return GeneratorState.STOPPED

    def get_status(self) -> dict:
        """Return pipeline status with child stream details."""
        streams = []
        total_events = 0
        total_errors = 0
        for gen in self.generators:
            status = gen.get_status()
            streams.append(
                {
                    "name": gen.name,
                    "template": gen.config.template,
                    "state": status["state"],
                    "events_generated": status["statistics"]["events_generated"],
                    "errors": status["statistics"]["errors"],
                }
            )
            total_events += status["statistics"]["events_generated"]
            total_errors += status["statistics"]["errors"]

        return {
            "name": self.config.name,
            "enabled": self.config.enabled,
            "state": self.state.value,
            "timezone": self.config.timezone,
            "outputs": list(self.config.outputs),
            "schedule": self.config.schedule.model_dump(),
            "streams": streams,
            "statistics": {
                "events_generated": total_events,
                "errors": total_errors,
            },
        }
