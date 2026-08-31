"""Generator engine core - manages all generators."""

import hashlib
import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from meltr.core.config import INTERNAL_LOGS_TEMPLATE_SENTINEL, Config, GeneratorConfig
from meltr.core.generator import Generator, GeneratorState
from meltr.core.internal_log_generator import (
    INTERNAL_LOGS_GENERATOR_NAME,
    InternalLogGenerator,
)
from meltr.entities.registry import EntityRegistry
from meltr.outputs.factory import create_output_handlers
from meltr.templates.cache import TemplateCache
from meltr.templates.loader import TemplateLoader
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class Engine:
    """Manages all generators and their lifecycle."""

    def __init__(self, config: Config, registry: EntityRegistry) -> None:
        """Initialize engine.

        Args:
            config: Configuration object
            registry: Entity registry instance
        """
        self.config = config
        self.registry = registry

        # Template system
        template_loader = TemplateLoader(config)
        self.template_cache = TemplateCache(template_loader, config.templates.cache_ttl)

        # Generators (template-based and internal log generator)
        self._generators: dict[str, Generator | InternalLogGenerator] = {}
        self._generators_lock = threading.Lock()

        # Thread pool
        self._thread_pool: ThreadPoolExecutor | None = None
        self._generator_futures: dict[str, Future] = {}
        self._monitor_timer: threading.Timer | None = None
        self._monitoring_active = True

        # Load generators from config
        self.load_generators_from_config()

        # Start background exception monitoring
        self._start_exception_monitoring()

    def _calculate_thread_pool_size(self) -> int:
        """Calculate thread pool size.

        Returns:
            Thread pool size
        """
        if self.config.engine.thread_pool_size is not None:
            return self.config.engine.thread_pool_size

        # Auto: CPU cores × 5
        cpu_count = os.cpu_count() or 4
        return cpu_count * 5

    def _should_materialize_internal_logs(self, gen_config: GeneratorConfig) -> bool:
        """Return True when reserved internal-logs entry should be loaded."""
        return (
            gen_config.name == INTERNAL_LOGS_GENERATOR_NAME
            and gen_config.enabled
            and bool(gen_config.outputs)
        )

    def _create_internal_log_generator(
        self, gen_config: GeneratorConfig, config: Config
    ) -> InternalLogGenerator:
        output_handlers = create_output_handlers(
            gen_config.outputs,
            config.outputs.definitions,
            retry_config=config.outputs.retry,
            buffer_size=config.outputs.buffer_size,
        )
        return InternalLogGenerator(output_handlers=output_handlers)

    def _create_template_generator(self, gen_config: GeneratorConfig, config: Config) -> Generator:
        template_info = self.template_cache.get_template(gen_config.template)
        if not template_info:
            raise ValueError(f"Template not found: {gen_config.template}")

        output_handlers = create_output_handlers(
            gen_config.outputs,
            config.outputs.definitions,
            retry_config=config.outputs.retry,
            buffer_size=config.outputs.buffer_size,
        )

        return Generator(
            name=gen_config.name,
            config=gen_config,
            template_loader=TemplateLoader(config),
            registry=self.registry,
            output_handlers=output_handlers,
        )

    def load_generators_from_config(self) -> None:
        """Load generator configurations and create Generator instances."""
        with self._generators_lock:
            # Clear existing generators
            for generator in self._generators.values():
                if generator.state != GeneratorState.STOPPED:
                    generator.stop()
            self._generators.clear()

            # Create generators from config
            for gen_config in self.config.generators:
                try:
                    if gen_config.name == INTERNAL_LOGS_GENERATOR_NAME:
                        if not self._should_materialize_internal_logs(gen_config):
                            continue
                        internal_gen = self._create_internal_log_generator(gen_config, self.config)
                        self._generators[INTERNAL_LOGS_GENERATOR_NAME] = internal_gen
                        logger.info(f"Loaded generator: {INTERNAL_LOGS_GENERATOR_NAME}")
                        continue

                    if gen_config.template == INTERNAL_LOGS_TEMPLATE_SENTINEL:
                        continue

                    generator = self._create_template_generator(gen_config, self.config)
                    self._generators[gen_config.name] = generator
                    logger.info(f"Loaded generator: {gen_config.name}")

                except Exception as e:
                    logger.error(f"Failed to load generator {gen_config.name}: {e}", exc_info=True)

    def reload_config(self, new_config: Config) -> dict[str, Any]:
        """Reload configuration and apply changes dynamically.

        Detects added/removed generators and starts/stops them accordingly.
        Updates existing generators if their config changed.

        Args:
            new_config: New configuration object

        Returns:
            Dictionary with reload results (added, removed, updated, errors)
        """

        results = {
            "added": [],
            "removed": [],
            "updated": [],
            "errors": [],
        }

        # Update config reference
        old_config = self.config
        self.config = new_config

        # Update template cache config
        self.template_cache.loader.config = new_config

        def _fingerprint_output_def(output_def: Any) -> str:
            """Stable fingerprint for output destination definitions.

            Used to detect when referenced output definitions changed so running
            generators can be recreated immediately.
            """
            try:
                # Pydantic models provide a consistent JSON representation.
                dumped = output_def.model_dump(
                    mode="json",
                    exclude_none=False,
                    exclude_unset=False,
                    exclude_defaults=False,
                )
                payload = json.dumps(dumped, sort_keys=True, separators=(",", ":"))
            except Exception:
                # Last-resort stable fallback; should never crash reload_config.
                try:
                    payload = repr(output_def)
                except Exception:
                    payload = f"<unfingerprintable {type(output_def).__name__}>"
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()

        old_fp_by_name = {
            d.name: _fingerprint_output_def(d)
            for d in (getattr(old_config.outputs, "definitions", None) or [])
        }
        new_fp_by_name = {
            d.name: _fingerprint_output_def(d)
            for d in (getattr(new_config.outputs, "definitions", None) or [])
        }

        # Get current generator names
        with self._generators_lock:
            current_names = set(self._generators.keys())

        # Get new generator names from config
        new_gen_configs = {gen.name: gen for gen in new_config.generators}
        new_names = set(new_gen_configs.keys())

        # Find removed generators
        removed_names = current_names - new_names
        for name in removed_names:
            try:
                logger.info(f"Stopping removed generator: {name}")
                self.stop_generator(name)
                with self._generators_lock:
                    if name in self._generators:
                        del self._generators[name]
                    self._generator_futures.pop(name, None)
                results["removed"].append(name)
            except Exception as e:
                logger.error(f"Error removing generator {name}: {e}", exc_info=True)
                results["errors"].append(f"Failed to remove {name}: {e}")

        # Find added generators
        added_names = new_names - current_names
        for name in added_names:
            try:
                gen_config = new_gen_configs[name]
                logger.info(f"Adding new generator: {name}")

                if name == INTERNAL_LOGS_GENERATOR_NAME:
                    if not self._should_materialize_internal_logs(gen_config):
                        continue
                    generator = self._create_internal_log_generator(gen_config, new_config)
                elif gen_config.template == INTERNAL_LOGS_TEMPLATE_SENTINEL:
                    continue
                else:
                    generator = self._create_template_generator(gen_config, new_config)

                with self._generators_lock:
                    self._generators[name] = generator

                if gen_config.enabled:
                    logger.info(f"Starting newly added generator: {name}")
                    self.start_generator(name)

                results["added"].append(name)
            except Exception as e:
                logger.error(f"Error adding generator {name}: {e}", exc_info=True)
                results["errors"].append(f"Failed to add {name}: {e}")

        # Check for updated generators (config changed)
        updated_names = current_names & new_names
        for name in updated_names:
            try:
                new_gen_config = new_gen_configs[name]

                if name == INTERNAL_LOGS_GENERATOR_NAME:
                    with self._generators_lock:
                        old_gen = self._generators.get(name)

                    if not self._should_materialize_internal_logs(new_gen_config):
                        if old_gen:
                            self.stop_generator(name)
                            with self._generators_lock:
                                self._generators.pop(name, None)
                                self._generator_futures.pop(name, None)
                            results["removed"].append(name)
                        continue

                    if not old_gen:
                        continue

                    old_gen_config = next(
                        (g for g in old_config.generators if g.name == name), None
                    )
                    old_config_dict = old_gen_config.model_dump() if old_gen_config else {}
                    new_config_dict = new_gen_config.model_dump()
                    old_referenced_output_fps = [
                        old_fp_by_name.get(out_name, "MISSING")
                        for out_name in new_gen_config.outputs
                    ]
                    new_referenced_output_fps = [
                        new_fp_by_name.get(out_name, "MISSING")
                        for out_name in new_gen_config.outputs
                    ]

                    if (
                        old_config_dict != new_config_dict
                        or old_referenced_output_fps != new_referenced_output_fps
                    ):
                        logger.info(f"Updating generator config: {name}")
                        was_running = old_gen.state in (
                            GeneratorState.RUNNING,
                            GeneratorState.STARTING,
                        )
                        if was_running:
                            self.stop_generator(name)

                        new_generator = self._create_internal_log_generator(
                            new_gen_config, new_config
                        )
                        with self._generators_lock:
                            self._generators[name] = new_generator
                            self._generator_futures.pop(name, None)

                        # Only restart if it was already running. Do not start dormant
                        # enabled generators — that leaks log-forwarding/HTTP workers.
                        if was_running:
                            logger.info(f"Restarting updated generator: {name}")
                            self.start_generator(name)

                        results["updated"].append(name)
                    continue

                with self._generators_lock:
                    old_gen = self._generators.get(name)

                if not old_gen:
                    continue

                if new_gen_config.template == INTERNAL_LOGS_TEMPLATE_SENTINEL:
                    continue

                # Check if generator config changed (simple comparison)
                old_config_dict = old_gen.config.model_dump()
                new_config_dict = new_gen_config.model_dump()

                # Detect output-definition changes even when generator config is identical.
                old_referenced_output_fps = [
                    old_fp_by_name.get(out_name, "MISSING") for out_name in new_gen_config.outputs
                ]
                new_referenced_output_fps = [
                    new_fp_by_name.get(out_name, "MISSING") for out_name in new_gen_config.outputs
                ]

                if (
                    old_config_dict != new_config_dict
                    or old_referenced_output_fps != new_referenced_output_fps
                ):
                    logger.info(f"Updating generator config: {name}")

                    # Stop if running
                    was_running = old_gen.state in (GeneratorState.RUNNING, GeneratorState.STARTING)
                    if was_running:
                        self.stop_generator(name)

                    new_generator = self._create_template_generator(new_gen_config, new_config)

                    with self._generators_lock:
                        self._generators[name] = new_generator
                        self._generator_futures.pop(name, None)

                    # Only restart if it was already running (same as internal-logs).
                    if was_running:
                        logger.info(f"Restarting updated generator: {name}")
                        self.start_generator(name)

                    results["updated"].append(name)
            except Exception as e:
                logger.error(f"Error updating generator {name}: {e}", exc_info=True)
                results["errors"].append(f"Failed to update {name}: {e}")

        logger.info(
            f"Config reloaded: {len(results['added'])} added, "
            f"{len(results['removed'])} removed, {len(results['updated'])} updated"
        )

        return results

    def start_generator(self, name: str) -> None:
        """Start a generator.

        Args:
            name: Generator name

        Raises:
            KeyError: If generator not found
            RuntimeError: If generator cannot start
        """
        with self._generators_lock:
            if name not in self._generators:
                raise KeyError(f"Generator not found: {name}")

            generator = self._generators[name]

            # Check if already running
            if generator.state in (GeneratorState.RUNNING, GeneratorState.STARTING):
                logger.warning(f"Generator {name} is already running")
                return

            # Internal log generator runs its own loop in start(); no thread pool
            if name == INTERNAL_LOGS_GENERATOR_NAME:
                try:
                    generator.start()
                except Exception as e:
                    logger.error(f"Failed to start generator {name}: {e}", exc_info=True)
                    raise
                return

            # Ensure thread pool exists
            if self._thread_pool is None:
                pool_size = self._calculate_thread_pool_size()
                self._thread_pool = ThreadPoolExecutor(
                    max_workers=pool_size, thread_name_prefix="meltr-generator"
                )
                logger.info(f"Created thread pool with {pool_size} workers")

        # Release _generators_lock before submit/sleep so done callbacks cannot deadlock.
        try:
            generator.start()

            future = self._thread_pool.submit(generator._generate_loop)
            future.add_done_callback(
                lambda done_future, generator_name=name: self._handle_generator_future_done(
                    generator_name, done_future
                )
            )
            with self._generators_lock:
                self._generator_futures[name] = future

            import time

            time.sleep(0.1)
            if future.done():
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Generator {name} loop crashed immediately: {e}", exc_info=True)
                    generator._transition_to(GeneratorState.ERROR)
                    raise RuntimeError(f"Generator {name} loop failed to start: {e}") from e

        except Exception as e:
            logger.error(f"Failed to start generator {name}: {e}", exc_info=True)
            raise

    def _handle_generator_future_done(self, name: str, future: Future) -> None:
        """Handle completed generator future and mark failures immediately."""
        try:
            future.result()
        except Exception as e:
            logger.error(f"Generator {name} loop crashed: {e}", exc_info=True)
            with self._generators_lock:
                generator = self._generators.get(name)
                if generator:
                    try:
                        generator._transition_to(GeneratorState.ERROR)
                    except Exception as transition_error:
                        logger.error(
                            f"Failed to transition generator {name} to ERROR: {transition_error}"
                        )
                self._generator_futures.pop(name, None)
            return

        with self._generators_lock:
            self._generator_futures.pop(name, None)

    def stop_generator(self, name: str) -> None:
        """Stop a generator.

        Args:
            name: Generator name
        """
        with self._generators_lock:
            if name not in self._generators:
                logger.warning(f"Generator not found: {name}")
                return

            generator = self._generators[name]
            generator.stop()

            # Remove future
            self._generator_futures.pop(name, None)

    def restart_generator(self, name: str) -> None:
        """Restart a generator.

        Args:
            name: Generator name
        """
        self.stop_generator(name)
        # Wait a moment
        import time

        time.sleep(0.5)
        self.start_generator(name)

    def _start_exception_monitoring(self) -> None:
        """Start background timer to check for generator loop exceptions."""
        self._monitoring_active = True
        self._schedule_exception_check()

    def _schedule_exception_check(self) -> None:
        """Schedule next exception check."""
        if not self._monitoring_active:
            return

        def check_futures() -> None:
            """Check futures and reschedule."""
            self._check_future_exceptions()
            # Reschedule if still active
            if self._monitoring_active:
                self._schedule_exception_check()

        self._monitor_timer = threading.Timer(5.0, check_futures)
        self._monitor_timer.daemon = True
        self._monitor_timer.start()

    def _check_future_exceptions(self) -> None:
        """Check all generator futures for exceptions.

        This should be called periodically to catch generator loop crashes.
        """
        futures_to_remove = []
        # Don't hold lock while checking futures - just get a snapshot
        futures_snapshot = dict(self._generator_futures)

        for name, future in futures_snapshot.items():
            if future.done():
                try:
                    future.result()  # Will raise if exception occurred (non-blocking for done futures)
                except Exception as e:
                    logger.error(f"Generator {name} loop crashed: {e}", exc_info=True)
                    # Transition to ERROR state (needs lock)
                    with self._generators_lock:
                        if name in self._generators:
                            try:
                                self._generators[name]._transition_to(GeneratorState.ERROR)
                            except Exception as transition_error:
                                logger.error(
                                    f"Failed to transition generator {name} to ERROR: {transition_error}"
                                )
                    futures_to_remove.append(name)

        # Remove completed/failed futures (needs lock)
        if futures_to_remove:
            with self._generators_lock:
                for name in futures_to_remove:
                    self._generator_futures.pop(name, None)

    def get_generator_status(self, name: str | None = None) -> dict:
        """Get generator status.

        Args:
            name: Generator name (None for all generators)

        Returns:
            Status dictionary
        """
        # Check for future exceptions before getting status
        self._check_future_exceptions()

        # CRITICAL: Release lock before calling get_status() to avoid deadlock
        # get_status() calls handler.get_statistics() which acquires handler locks
        # If generator thread holds handler locks, deadlock occurs
        with self._generators_lock:
            if name:
                if name not in self._generators:
                    raise KeyError(f"Generator not found: {name}")
                generator = self._generators[name]
            else:
                generators = list(self._generators.values())

        # Call get_status() OUTSIDE of lock to prevent deadlock
        if name:
            return generator.get_status()
        else:
            return {"generators": [gen.get_status() for gen in generators]}

    def get_all_generators(self) -> list[Generator | InternalLogGenerator]:
        """Get all generator instances.

        Returns:
            List of Generator objects (safe to use without lock)

        Note: Dict access is atomic in CPython, so no lock needed for read-only access.
        Callers should not modify the returned list or generators.
        """
        # CRITICAL: No lock - dict.values() is atomic in CPython for reads
        # Holding lock here causes deadlock when API thread holds it while generator
        # thread needs it, or vice versa
        return list(self._generators.values())

    def shutdown(self) -> None:
        """Shutdown engine and all generators."""
        logger.info("Shutting down engine...")

        # Stop exception monitoring
        self._monitoring_active = False
        if self._monitor_timer:
            self._monitor_timer.cancel()
            self._monitor_timer = None

        # Stop all generators
        with self._generators_lock:
            for generator in self._generators.values():
                generator.stop()

        # Shutdown thread pool
        if self._thread_pool:
            # timeout parameter available in Python 3.9+, but handle compatibility
            # Some Python 3.9.x versions may not support timeout parameter
            try:
                self._thread_pool.shutdown(wait=True, timeout=30.0)
            except TypeError:
                # Fallback if timeout not supported in this Python version
                self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

        logger.info("Engine shutdown complete")
