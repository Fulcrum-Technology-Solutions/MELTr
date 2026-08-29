"""FastAPI application and server lifecycle management."""

import threading
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from meltr.api.auth import resolve_api_key
from meltr.core.config import Config
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class APIServer:
    """Manages FastAPI server lifecycle in background thread."""

    def __init__(self, config: Config) -> None:
        """Initialize API server.

        Args:
            config: Configuration object
        """
        self.config = config
        from meltr import __version__

        self.app = FastAPI(
            title="MELTr Management API",
            version=__version__,
            description="API for managing LogForge synthetic event log generation",
        )
        self.server_thread: threading.Thread | None = None
        self.server: uvicorn.Server | None = None
        self.start_time: float | None = None
        self._thread_error: BaseException | None = None
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """Configure CORS and other middleware."""
        origins = list(self.config.api.cors_origins)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=bool(origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Register API routes."""
        from meltr.api.endpoints import (
            community,
            entities,
            generators,
            health,
            pipelines,
            templates,
        )

        # Store server instance in app state for dependency injection
        self.app.state.server = self

        # Register routers
        self.app.include_router(health.router)
        self.app.include_router(entities.router)
        self.app.include_router(templates.router)
        self.app.include_router(community.router)
        self.app.include_router(generators.router)
        self.app.include_router(pipelines.router)

        @self.app.get("/api/metrics", response_class=PlainTextResponse)
        async def metrics(request: Request) -> str:
            """Prometheus metrics endpoint."""
            from meltr.api.auth import require_api_key

            await require_api_key(request)
            lines = ["# LogForge output pipeline metrics"]
            engine = getattr(request.app.state, "engine", None)
            if engine:
                try:
                    from meltr.api.endpoints.health import _collect_output_handlers

                    for h in _collect_output_handlers(engine):
                        if hasattr(h, "get_statistics"):
                            st = h.get_statistics()
                            name = st.get("name", getattr(h, "name", "unknown")).replace('"', '\\"')
                            lines.append(
                                f'logforge_output_backlog_size{{output="{name}"}} {st.get("backlog_size", 0)}'
                            )
                            lines.append(
                                f'logforge_output_dropped_total{{output="{name}"}} {st.get("dropped_count", 0)}'
                            )
                except Exception:
                    pass
            return "\n".join(lines) + "\n"

    def get_uptime(self) -> int:
        """Get server uptime in seconds.

        Returns:
            Uptime in seconds, or 0 if not started
        """
        if self.start_time is None:
            return 0
        return int(time.time() - self.start_time)

    def start(self) -> None:
        """Start API server in background thread."""
        if self.server_thread is not None and self.server_thread.is_alive():
            logger.warning("API server already running")
            return
        if self.server_thread is not None and not self.server_thread.is_alive():
            self.server_thread = None
            self.server = None

        api_config = self.config.api

        if not api_config.enabled:
            logger.info("API server disabled in configuration")
            return

        if self.config.api.auth.enabled and resolve_api_key(self.config) is None:
            raise RuntimeError("API auth enabled but no API key configured")

        self._thread_error = None

        def run_server() -> None:
            """Run uvicorn server in thread."""
            try:
                self.server = uvicorn.Server(
                    uvicorn.Config(
                        app=self.app,
                        host=api_config.host,
                        port=api_config.port,
                        log_config=None,  # Use our logging
                    )
                )
                self.start_time = time.time()
                logger.info(f"Starting API server on {api_config.host}:{api_config.port}")
                self.server.run()
            except Exception as e:
                self._thread_error = e
                logger.error(f"API server error: {e}", exc_info=True)

        self.server_thread = threading.Thread(
            target=run_server, daemon=True, name="logforge-api-server"
        )
        self.server_thread.start()

        # Wait a moment for server to start
        time.sleep(0.5)
        logger.info("API server started in background thread")

    def stop(self) -> None:
        """Stop API server gracefully."""
        if self.server is None:
            return

        logger.info("Stopping API server...")
        if self.server:
            self.server.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)

        self.start_time = None
        logger.info("API server stopped")

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server thread is alive
        """
        if self._thread_error is not None:
            return False
        return self.server_thread is not None and self.server_thread.is_alive()
