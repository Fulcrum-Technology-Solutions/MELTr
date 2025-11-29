"""Generator engine core - manages all generators."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional

from logforge.core.config import Config
from logforge.core.generator import Generator, GeneratorState
from logforge.entities.registry import EntityRegistry
from logforge.outputs.factory import create_output_handlers
from logforge.templates.cache import TemplateCache
from logforge.templates.loader import TemplateLoader
from logforge.utils.logging import get_logger

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
        
        # Generators
        self._generators: Dict[str, Generator] = {}
        self._generators_lock = threading.Lock()
        
        # Thread pool
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._generator_futures: Dict[str, Future] = {}
        
        # Load generators from config
        self.load_generators_from_config()
    
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
                    # Validate template exists
                    template_info = self.template_cache.get_template(gen_config.template)
                    if not template_info:
                        logger.warning(
                            f"Generator {gen_config.name}: Template not found: {gen_config.template}"
                        )
                        continue
                    
                    # Create output handlers
                    output_handlers = create_output_handlers(
                        gen_config.outputs,
                        self.config.outputs.definitions,
                        retry_config=self.config.outputs.retry,
                        buffer_size=self.config.outputs.buffer_size,
                    )
                    
                    # Create generator
                    generator = Generator(
                        name=gen_config.name,
                        config=gen_config,
                        template_loader=TemplateLoader(self.config),
                        registry=self.registry,
                        output_handlers=output_handlers,
                    )
                    
                    self._generators[gen_config.name] = generator
                    logger.info(f"Loaded generator: {gen_config.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load generator {gen_config.name}: {e}", exc_info=True)
    
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
            
            # Ensure thread pool exists
            if self._thread_pool is None:
                pool_size = self._calculate_thread_pool_size()
                self._thread_pool = ThreadPoolExecutor(
                    max_workers=pool_size,
                    thread_name_prefix="logforge-generator"
                )
                logger.info(f"Created thread pool with {pool_size} workers")
            
            # Start generator
            try:
                generator.start()
                
                # Submit generation loop to thread pool
                # The generator's start() initializes everything, then we run the loop
                future = self._thread_pool.submit(generator._generate_loop)
                self._generator_futures[name] = future
                
                # Check for immediate exceptions (generator loop crashes on startup)
                # Use a small delay to catch initialization errors
                import time
                time.sleep(0.1)  # Brief delay to catch immediate crashes
                if future.done():
                    try:
                        future.result()  # Will raise exception if one occurred
                    except Exception as e:
                        logger.error(
                            f"Generator {name} loop crashed immediately: {e}",
                            exc_info=True
                        )
                        generator._transition_to(GeneratorState.ERROR)
                        raise RuntimeError(f"Generator {name} loop failed to start: {e}")
                
            except Exception as e:
                logger.error(f"Failed to start generator {name}: {e}", exc_info=True)
                raise
    
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
    
    def _check_future_exceptions(self) -> None:
        """Check all generator futures for exceptions.
        
        This should be called periodically to catch generator loop crashes.
        """
        futures_to_remove = []
        with self._generators_lock:
            for name, future in self._generator_futures.items():
                if future.done():
                    try:
                        future.result()  # Will raise if exception occurred
                    except Exception as e:
                        logger.error(
                            f"Generator {name} loop crashed: {e}",
                            exc_info=True
                        )
                        if name in self._generators:
                            self._generators[name]._transition_to(GeneratorState.ERROR)
                        futures_to_remove.append(name)
        
        # Remove completed/failed futures outside of lock
        for name in futures_to_remove:
            self._generator_futures.pop(name, None)
    
    def get_generator_status(self, name: Optional[str] = None) -> Dict:
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
            return {
                "generators": [
                    gen.get_status() for gen in generators
                ]
            }
    
    def get_all_generators(self) -> List[Generator]:
        """Get all generator instances.
        
        Returns:
            List of Generator objects
        """
        with self._generators_lock:
            return list(self._generators.values())
    
    def shutdown(self) -> None:
        """Shutdown engine and all generators."""
        logger.info("Shutting down engine...")
        
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

