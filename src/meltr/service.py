"""MELTr service entry point - initializes and runs the service."""

import signal
import sys
from pathlib import Path

from meltr.api.server import APIServer
from meltr.core.config import load_config
from meltr.core.engine import Engine
from meltr.entities.registry import EntityRegistry
from meltr.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class MeltrService:
    """Main MELTr service that manages engine and API server."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize service.

        Args:
            config_path: Optional path to config file

        Raises:
            Exception: If initialization fails
        """
        # Ensure MELTR_HOME is set (self-discovery if not set)
        import os

        if not os.getenv("MELTR_HOME"):
            from meltr.core.paths import get_meltr_home

            discovered_home = get_meltr_home()
            os.environ["MELTR_HOME"] = str(discovered_home)
            logger.info(f"Set MELTR_HOME={discovered_home} (self-discovered)")

        try:
            # Load configuration
            self.config = load_config(config_path)
            logger.info(f"Configuration loaded from: {config_path or 'default'}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
            raise

        try:
            # Setup logging
            setup_logging(self.config)
            logger.info("MELTr service initializing...")
        except Exception as e:
            # If logging setup fails, print to stderr
            import sys

            print(f"ERROR: Failed to setup logging: {e}", file=sys.stderr)
            raise

        try:
            # Initialize entity registry
            self.registry = EntityRegistry(self.config)
            logger.info("Entity registry initialized")
        except Exception as e:
            logger.error(f"Failed to initialize entity registry: {e}", exc_info=True)
            raise

        try:
            # Initialize engine
            self.engine = Engine(self.config, self.registry)
            logger.info("Generator engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}", exc_info=True)
            raise

        try:
            # Initialize API server
            self.api_server = APIServer(self.config)

            # Store in app state for dependency injection
            self.api_server.app.state.engine = self.engine
            self.api_server.app.state.registry = self.registry
            self.api_server.app.state.template_cache = self.engine.template_cache
        except Exception as e:
            logger.error(f"Failed to initialize API server: {e}", exc_info=True)
            raise

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Start the service."""
        logger.info("Starting MELTr service...")

        # Start API server
        self.api_server.start()

        # Wait for API to be healthy
        import time

        time.sleep(1.0)

        if not self.api_server.is_running():
            err = getattr(self.api_server, "_thread_error", None)
            if err is not None:
                logger.error("API server exited before becoming ready: %s", err)
            else:
                logger.error("API server thread stopped unexpectedly")
            logger.error(
                "If the address is already in use, stop the other process (e.g. "
                "`pgrep -af 'python3.11 -m meltr'` then `kill <pid>`) or change "
                "`api.host` / `api.port` in config.yaml."
            )
            if err is not None:
                raise RuntimeError("API server failed to start") from err
            raise RuntimeError("API server failed to start")

        logger.info("MELTr service started successfully")
        logger.info(f"API server running on {self.config.api.host}:{self.config.api.port}")

        # Start enabled generators (including reserved internal-logs when materialized)
        from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME

        for gen_config in self.config.generators:
            if not gen_config.enabled:
                continue
            if gen_config.name not in self.engine._generators:
                if gen_config.name == INTERNAL_LOGS_GENERATOR_NAME:
                    continue
                logger.warning(
                    "Enabled generator %s was not loaded; skipping start",
                    gen_config.name,
                )
                continue
            try:
                self.engine.start_generator(gen_config.name)
                logger.info(f"Started generator: {gen_config.name}")
            except KeyError as e:
                logger.error(
                    "Unexpected KeyError starting generator %s: %s",
                    gen_config.name,
                    e,
                    exc_info=True,
                )
            except Exception as e:
                logger.error(f"Failed to start generator {gen_config.name}: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop the service."""
        logger.info("Stopping MELTr service...")

        # Shutdown engine
        self.engine.shutdown()

        # Stop API server
        self.api_server.stop()

        # Close registry
        self.registry.close()

        logger.info("MELTr service stopped")

    def run(self) -> None:
        """Run service (blocking)."""
        from meltr.core.pidfile import remove_service_pidfile, write_service_pidfile

        pidfile_written = False
        try:
            self.start()
            write_service_pidfile()
            pidfile_written = True

            # Keep service running
            import time

            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            raise
        finally:
            try:
                self.stop()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
            if pidfile_written:
                remove_service_pidfile()


def main() -> None:
    """Main entry point for service."""
    import argparse

    parser = argparse.ArgumentParser(description="MELTr synthetic event log generator service")
    parser.add_argument(
        "--config", type=Path, help="Path to config file (must be within MELTR_HOME)"
    )
    parser.add_argument("--host", type=str, help="API server host (overrides config)")
    parser.add_argument("--port", type=int, help="API server port (overrides config)")

    args = parser.parse_args()

    # Create and run service
    service = MeltrService(config_path=args.config)

    # Override config if provided
    if args.host:
        service.config.api.host = args.host
    if args.port:
        service.config.api.port = args.port

    service.run()
