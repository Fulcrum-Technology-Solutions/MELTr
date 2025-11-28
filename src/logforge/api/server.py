"""FastAPI application and server lifecycle management."""

import threading
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logforge.core.config import Config
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class APIServer:
    """Manages FastAPI server lifecycle in background thread."""
    
    def __init__(self, config: Config) -> None:
        """Initialize API server.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.app = FastAPI(
            title="LogForge Management API",
            version="1.0.0",
            description="API for managing LogForge synthetic event log generation",
        )
        self.server_thread: Optional[threading.Thread] = None
        self.server: Optional[uvicorn.Server] = None
        self.start_time: Optional[float] = None
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self) -> None:
        """Configure CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # TODO: Make configurable
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self) -> None:
        """Register API routes."""
        from logforge.api.endpoints import entities, generators, health, templates
        
        # Store server instance in app state for dependency injection
        self.app.state.server = self
        
        # Register routers
        self.app.include_router(health.router)
        self.app.include_router(entities.router)
        self.app.include_router(templates.router)
        self.app.include_router(generators.router)
        
        # Metrics endpoint (will be moved to separate module later)
        @self.app.get("/api/metrics")
        async def metrics() -> str:
            """Prometheus metrics endpoint."""
            # TODO: Return Prometheus format metrics
            return "# LogForge metrics\n# TODO: Implement metrics collection\n"
    
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
        
        api_config = self.config.api
        
        if not api_config.enabled:
            logger.info("API server disabled in configuration")
            return
        
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
                logger.error(f"API server error: {e}", exc_info=True)
        
        self.server_thread = threading.Thread(
            target=run_server,
            daemon=True,
            name="logforge-api-server"
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
        return self.server_thread is not None and self.server_thread.is_alive()

