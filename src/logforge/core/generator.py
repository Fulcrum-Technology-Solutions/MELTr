"""Generator class with state machine and lifecycle management."""

import threading
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from logforge.core.config import GeneratorConfig
from logforge.core.frequency import calculate_rate
from logforge.entities.registry import EntityRegistry
from logforge.outputs.base import OutputHandler
from logforge.templates.loader import TemplateLoader
from logforge.templates.renderer import TemplateRenderer
from logforge.utils.logging import get_logger

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
VALID_TRANSITIONS: Dict[GeneratorState, List[GeneratorState]] = {
    GeneratorState.STOPPED: [GeneratorState.STARTING],
    GeneratorState.STARTING: [GeneratorState.RUNNING, GeneratorState.ERROR, GeneratorState.STOPPED],
    GeneratorState.RUNNING: [GeneratorState.STOPPING, GeneratorState.DEGRADED, GeneratorState.ERROR],
    GeneratorState.DEGRADED: [GeneratorState.RUNNING, GeneratorState.ERROR, GeneratorState.STOPPING],
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
        output_handlers: List[OutputHandler],
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
        
        # State management
        self._state = GeneratorState.STOPPED
        self._state_lock = threading.Lock()
        
        # Generation control
        self._stop_event = threading.Event()
        
        # Statistics
        self._events_generated = 0
        self._errors = 0
        self._start_time: Optional[float] = None
        self._last_event_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._stats_lock = threading.Lock()
        
        # Template renderer
        self._renderer: Optional[TemplateRenderer] = None
        self._template_content: Optional[str] = None
        self._template_info: Optional[Any] = None  # TemplateInfo object
    
    @property
    def state(self) -> GeneratorState:
        """Get current generator state."""
        with self._state_lock:
            return self._state
    
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
            with template_info.template_path.open('r', encoding='utf-8') as f:
                self._template_content = f.read()
            
            # Create renderer
            self._renderer = TemplateRenderer(self.registry)
            
            # Initialize output handlers with template context
            for handler in self.output_handlers:
                try:
                    # Pass template context to file output handlers
                    if hasattr(handler, 'set_template_context'):
                        template_metadata = {
                            "vendor": template_info.vendor,
                            "product": template_info.product,
                            "data_source": template_info.data_source,
                        }
                        # Note: collection is not part of the template ID structure
                        # Template ID format: vendor/product/data_source/template_name
                        # If collection is needed, it would need to be added to metadata
                        
                        organization_name = None
                        try:
                            org = self.registry.get_organization()
                            if org and 'name' in org:
                                organization_name = org['name']
                        except Exception:
                            pass  # Organization not available
                        
                        handler.set_template_context(
                            generator_name=self.name,
                            output_name=handler.name,
                            template_metadata=template_metadata,
                            organization_name=organization_name,
                        )
                    
                    # Output handlers should have an initialize method if needed
                    if hasattr(handler, 'initialize'):
                        handler.initialize()
                except Exception as e:
                    logger.error(f"Generator {self.name}: Failed to initialize output handler: {e}")
                    raise
            
            # Clear stop event (generation loop will be started by engine)
            self._stop_event.clear()
            
            # Transition to RUNNING after successful initialization
            if self._transition_to(GeneratorState.RUNNING):
                self._start_time = time.time()
                logger.info(f"Generator {self.name} initialized and ready")
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
        try:
            while not self._stop_event.is_set():
                # Calculate current rate
                rate = calculate_rate(self.config.frequency)
                
                if rate <= 0:
                    # Sleep and continue if rate is 0
                    time.sleep(1.0)
                    continue
                
                # Calculate sleep interval (events per second)
                sleep_interval = 1.0 / rate
                
                # Generate event
                try:
                    event = self._render_event()
                    if event:
                        self._write_to_outputs(event)
                        with self._stats_lock:
                            self._events_generated += 1
                            self._last_event_time = time.time()
                except Exception as e:
                    logger.error(f"Generator {self.name}: Error generating event: {e}", exc_info=True)
                    with self._stats_lock:
                        self._errors += 1
                        self._last_error = str(e)
                    
                    # Check if error should transition to ERROR state
                    # (template errors = ERROR, output errors = DEGRADED)
                    if "template" in str(e).lower() or "render" in str(e).lower():
                        self._transition_to(GeneratorState.ERROR)
                        break
                    else:
                        # Output error - transition to DEGRADED
                        if self.state == GeneratorState.RUNNING:
                            self._transition_to(GeneratorState.DEGRADED)
                
                # Sleep to maintain rate
                time.sleep(sleep_interval)
        
        except Exception as e:
            logger.error(f"Generator {self.name}: Generation loop error: {e}", exc_info=True)
            self._transition_to(GeneratorState.ERROR)
    
    def _render_event(self) -> Optional[str]:
        """Render a single event from template.
        
        Returns:
            Rendered event string or None on error
        """
        if not self._renderer or not self._template_content:
            raise RuntimeError("Renderer or template not initialized")
        
        return self._renderer.render_string(self._template_content)
    
    def _write_to_outputs(self, event: str) -> None:
        """Write event to all output handlers.
        
        Args:
            event: Event string to write
        """
        for handler in self.output_handlers:
            try:
                handler.write(event)
            except Exception as e:
                logger.warning(f"Generator {self.name}: Output handler write failed: {e}")
                # Don't raise - let other handlers try
                # State will transition to DEGRADED if all handlers fail
    
    def _validate_entities_available(self) -> None:
        """Validate that entities are available for generation.
        
        Raises:
            ValueError: If entities are missing or invalid
        """
        if not self.registry._data:
            raise ValueError("Entity registry is empty. Add entities before starting generators.")
        
        users = self.registry._data.get('users', [])
        devices = self.registry._data.get('devices', [])
        services = self.registry._data.get('services', [])
        
        if len(users) == 0:
            raise ValueError("At least one user is required to start generators. Import entities first.")
        if len(devices) == 0:
            raise ValueError("At least one device is required to start generators. Import entities first.")
        if len(services) == 0:
            raise ValueError("At least one service is required to start generators. Import entities first.")
    
    def get_statistics(self) -> Dict:
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
                "last_event": datetime.utcfromtimestamp(self._last_event_time).isoformat() + "Z" if self._last_event_time else None,
                "last_error": self._last_error,
            }
    
    def get_status(self) -> Dict:
        """Get generator status with full details.
        
        Returns:
            Dictionary with status information
        """
        stats = self.get_statistics()
        current_rate = calculate_rate(self.config.frequency) if self.state == GeneratorState.RUNNING else 0
        
        # Get output handler statistics
        output_stats = []
        for handler in self.output_handlers:
            if hasattr(handler, 'get_statistics'):
                try:
                    output_stats.append(handler.get_statistics())
                except Exception as e:
                    logger.warning(f"Generator {self.name}: Failed to get statistics for output {handler.name}: {e}")
                    # Fallback to basic info
                    output_stats.append({
                        "handler_name": handler.name if hasattr(handler, 'name') else 'unknown',
                        "handler_type": type(handler).__name__,
                        "health_status": "unknown",
                    })
            else:
                # Handler doesn't support statistics, provide basic info
                output_stats.append({
                    "handler_name": handler.name if hasattr(handler, 'name') else 'unknown',
                    "handler_type": type(handler).__name__,
                    "health_status": "healthy" if handler.is_healthy() else "degraded",
                })
        
        return {
            "name": self.name,
            "state": self.state.value,
            "template": self.config.template,
            "enabled": self.config.enabled,
            "frequency": {
                "base_rate": self.config.frequency.base_rate,
                "current_rate": current_rate,
            },
            "outputs": [handler.name for handler in self.output_handlers if hasattr(handler, 'name')],
            "output_status": output_stats,
            "statistics": stats,
        }

