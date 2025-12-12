"""Template rendering engine with Jinja2 and Faker."""

from typing import Any, Dict, Optional

from faker import Faker
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from logforge.entities.registry import EntityRegistry
from logforge.templates.filters import register_filters
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class TemplateRenderer:
    """Renders Jinja2 templates with registry and Faker context."""
    
    def __init__(self, registry: EntityRegistry, timezone: Optional[str] = None) -> None:
        """Initialize template renderer.
        
        Args:
            registry: Entity registry instance
            timezone: Optional timezone override (e.g., 'America/New_York').
                     If not provided, uses organization timezone.
        """
        self.registry = registry
        self.faker = Faker()
        
        # Create sandboxed Jinja2 environment
        self.env = SandboxedEnvironment(
            loader=FileSystemLoader('/'),  # Will use absolute paths
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Register custom filters
        register_filters(self.env)
        
        # Get timezone (use provided timezone or fall back to organization timezone)
        if timezone is None:
            timezone = self.registry.get_organization_timezone()
        
        # Register timezone-aware now() function
        from logforge.templates.filters import now as now_func
        self.env.globals['now'] = lambda: now_func(timezone)
        self.env.globals['current_timestamp'] = lambda: now_func(timezone)
        
        # Add Faker to globals
        self.env.globals['fake'] = self.faker
        
        # Add registry functions to globals
        self._register_registry_functions()
    
    def _register_registry_functions(self) -> None:
        """Register entity registry functions in template context."""
        # Create a registry object with all functions
        registry_obj = {
            'get_random_user': lambda: self.registry.get_random_user() or {},
            'get_random_device': lambda: self.registry.get_random_device() or {},
            'get_random_service': lambda: self.registry.get_random_service() or {},
            'get_user': lambda username: self.registry.get_user(username),
            'get_device': lambda hostname: self.registry.get_device(hostname),
            'get_service': lambda name: self.registry.get_service(name),
            'get_organization': lambda: self.registry.get_organization(),
            'get_organization_field': lambda field: self.registry.get_organization_field(field),
            'get_organization_contact': lambda role: self.registry.get_organization_contact(role),
        }
        
        self.env.globals['registry'] = registry_obj
    
    def render_template(self, template_path: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a template file.
        
        Args:
            template_path: Path to template.j2 file
            context: Additional context variables (merged with registry/faker)
            
        Returns:
            Rendered template string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template rendering fails
        """
        try:
            # Load template from file
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = self.env.from_string(template_content)
            
            # Merge additional context
            render_context = context or {}
            
            # Render
            result = template.render(**render_context)
            return result
        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Template rendering failed: {e}") from e
    
    def render_string(self, template_string: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a template from string.
        
        Args:
            template_string: Template content as string
            context: Additional context variables
            
        Returns:
            Rendered template string
            
        Raises:
            ValueError: If template rendering fails
        """
        try:
            template = self.env.from_string(template_string)
            render_context = context or {}
            result = template.render(**render_context)
            return result
        except Exception as e:
            raise ValueError(f"Template rendering failed: {e}") from e

