"""LogForge service entry point - initializes and runs the service."""

import signal
import sys
from pathlib import Path
from typing import Optional

from logforge.api.server import APIServer
from logforge.core.config import load_config
from logforge.core.engine import Engine
from logforge.entities.registry import EntityRegistry
from logforge.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class LogForgeService:
    """Main LogForge service that manages engine and API server."""
    
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize service.
        
        Args:
            config_path: Optional path to config file
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Setup logging
        setup_logging(self.config)
        logger.info("LogForge service initializing...")
        
        # Initialize entity registry
        self.registry = EntityRegistry(self.config)
        logger.info("Entity registry initialized")
        
        # Initialize engine
        self.engine = Engine(self.config, self.registry)
        logger.info("Generator engine initialized")
        
        # Initialize API server
        self.api_server = APIServer(self.config)
        
        # Store in app state for dependency injection
        self.api_server.app.state.engine = self.engine
        self.api_server.app.state.registry = self.registry
        self.api_server.app.state.template_cache = self.engine.template_cache
        
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
        logger.info("Starting LogForge service...")
        
        # Start API server
        self.api_server.start()
        
        # Wait for API to be healthy
        import time
        time.sleep(1.0)
        
        if not self.api_server.is_running():
            logger.error("API server failed to start")
            raise RuntimeError("API server failed to start")
        
        logger.info("LogForge service started successfully")
        logger.info(f"API server running on {self.config.api.host}:{self.config.api.port}")
        
        # Start enabled generators
        for gen_config in self.config.generators:
            if gen_config.enabled:
                try:
                    self.engine.start_generator(gen_config.name)
                    logger.info(f"Started generator: {gen_config.name}")
                except Exception as e:
                    logger.error(f"Failed to start generator {gen_config.name}: {e}", exc_info=True)
    
    def stop(self) -> None:
        """Stop the service."""
        logger.info("Stopping LogForge service...")
        
        # Shutdown engine
        self.engine.shutdown()
        
        # Stop API server
        self.api_server.stop()
        
        # Close registry
        self.registry.close()
        
        logger.info("LogForge service stopped")
    
    def run(self) -> None:
        """Run service (blocking)."""
        try:
            self.start()
            
            # Keep service running
            import time
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()


def main() -> None:
    """Main entry point for service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LogForge synthetic event log generator service")
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to config file (must be within LOGFORGE_HOME)'
    )
    parser.add_argument(
        '--host',
        type=str,
        help='API server host (overrides config)'
    )
    parser.add_argument(
        '--port',
        type=int,
        help='API server port (overrides config)'
    )
    
    args = parser.parse_args()
    
    # Create and run service
    service = LogForgeService(config_path=args.config)
    
    # Override config if provided
    if args.host:
        service.config.api.host = args.host
    if args.port:
        service.config.api.port = args.port
    
    service.run()

