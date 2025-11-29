"""Path template resolver for file output handlers."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from logforge.core.paths import get_logforge_home
from logforge.utils.logging import get_logger

logger = get_logger(__name__)


class PathTemplateContext:
    """Context for resolving path templates."""
    
    def __init__(
        self,
        generator_name: str,
        output_name: str,
        template_metadata: Optional[Dict[str, Any]] = None,
        organization_name: Optional[str] = None,
        timezone: str = 'UTC',
    ) -> None:
        """Initialize path template context.
        
        Args:
            generator_name: Generator name
            output_name: Output handler name
            template_metadata: Template metadata dict (vendor, product, data_source, etc.)
            organization_name: Organization name from entity registry
            timezone: Timezone string (e.g., 'America/New_York'). Defaults to UTC.
        """
        self.generator_name = generator_name
        self.output_name = output_name
        self.template_metadata = template_metadata or {}
        self.organization_name = organization_name
        
        # Get current time in specified timezone
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            # Invalid timezone, fall back to UTC
            tz = ZoneInfo('UTC')
        self._now = datetime.now(tz)
    
    def get_variables(self) -> Dict[str, str]:
        """Get all available template variables.
        
        Returns:
            Dictionary of variable names to values
        """
        vars: Dict[str, str] = {
            # Generator context
            "generator": self.generator_name,
            "generator_name": self.generator_name,
            
            # Output context
            "output_name": self.output_name,
            
            # Time variables
            "date": self._now.strftime("%Y-%m-%d"),
            "year": self._now.strftime("%Y"),
            "month": self._now.strftime("%m"),
            "day": self._now.strftime("%d"),
            "hour": self._now.strftime("%H"),
            "minute": self._now.strftime("%M"),
            "timestamp": str(int(self._now.timestamp())),
            
            # Environment
            "LOGFORGE_HOME": str(get_logforge_home()),
        }
        
        # Template metadata variables
        if self.template_metadata:
            vars["vendor"] = self.template_metadata.get("vendor", "")
            vars["product"] = self.template_metadata.get("product", "")
            vars["data_source"] = self.template_metadata.get("data_source", "")
            # Collection is derived from template ID structure
            if "collection" in self.template_metadata:
                vars["collection"] = self.template_metadata["collection"]
        
        # Organization name
        if self.organization_name:
            vars["organization_name"] = self.organization_name
        
        return vars


def sanitize_filename_component(component: str) -> str:
    """Sanitize a filename component by removing invalid characters.
    
    Args:
        component: Filename component to sanitize
        
    Returns:
        Sanitized component safe for filesystem use
    """
    # Remove or replace invalid filesystem characters
    # Invalid on most filesystems: < > : " / \ | ? *
    invalid_chars = '<>:"/\\|?*'
    sanitized = component
    
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove leading/trailing dots and spaces (Windows issue)
    sanitized = sanitized.strip('. ')
    
    # Remove control characters
    sanitized = ''.join(c for c in sanitized if ord(c) >= 32)
    
    # Limit length (filesystem dependent, but 255 is safe)
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    return sanitized


def resolve_path_template(
    template: str,
    context: PathTemplateContext,
    sanitize: bool = True,
) -> Path:
    """Resolve a path template with variable substitution.
    
    Args:
        template: Path template string (supports {var} and ${VAR} syntax)
        context: Template context with available variables
        sanitize: Whether to sanitize template variable values
        
    Returns:
        Resolved Path object (absolute)
        
    Raises:
        ValueError: If template contains unresolved variables or invalid patterns
    """
    path = template
    variables = context.get_variables()
    
    # Step 1: Substitute ${VAR} patterns (environment variables)
    def replace_env_var(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name == 'LOGFORGE_HOME':
            return str(get_logforge_home())
        env_value = os.getenv(var_name, match.group(0))
        if env_value == match.group(0):
            logger.warning(f"Environment variable ${var_name} not found, using literal")
        return env_value
    
    env_pattern = r'\$\{([^}]+)\}'
    path = re.sub(env_pattern, replace_env_var, path)
    
    # Step 2: Substitute {var} patterns (template variables)
    def replace_template_var(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            value = str(variables[var_name])
            if sanitize:
                # Only sanitize if this looks like a filename component
                # Don't sanitize full paths or LOGFORGE_HOME
                if var_name not in ('LOGFORGE_HOME', 'path'):
                    value = sanitize_filename_component(value)
            return value
        else:
            logger.warning(f"Template variable {{{var_name}}} not found in context")
            return match.group(0)  # Keep original if not found
    
    template_pattern = r'\{([^}]+)\}'
    path = re.sub(template_pattern, replace_template_var, path)
    
    # Step 3: Check for unresolved variables
    if '{' in path or '${' in path:
        unresolved = re.findall(r'[{$]\{?([^}]+)\}?', path)
        logger.warning(f"Unresolved variables in path template: {unresolved}")
    
    # Step 4: Expand user home directory
    path = os.path.expanduser(path)
    
    # Step 5: Normalize path separators
    path = path.replace('\\', '/')
    
    # Step 6: Create Path object and resolve
    path_obj = Path(path)
    
    # Step 7: Validate and resolve to absolute path
    if not path_obj.is_absolute():
        # If path starts with 'logforge/', resolve relative to LOGFORGE_HOME
        if path_obj.parts and path_obj.parts[0] == 'logforge':
            path_obj = get_logforge_home() / Path(*path_obj.parts[1:])
        else:
            # Resolve relative to current working directory
            path_obj = Path.cwd() / path_obj
    
    # Step 8: Validate path doesn't contain directory traversal
    try:
        resolved = path_obj.resolve()
        # Check for directory traversal attempts
        if '..' in str(resolved):
            logger.warning(f"Path contains '..' after resolution: {resolved}")
    except (OSError, RuntimeError):
        # Path doesn't exist yet, but we can still validate structure
        if not path_obj.is_absolute():
            path_obj = Path.cwd() / path_obj
    
    logger.debug(f"Resolved path template '{template}' -> '{path_obj}'")
    return path_obj


def validate_path_template(template: str) -> tuple[bool, list[str]]:
    """Validate a path template for potential issues.
    
    Args:
        template: Path template string to validate
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Check for common issues
    if not template:
        return False, ["Path template is empty"]
    
    # Check for directory traversal attempts
    if '../' in template or '..\\' in template:
        warnings.append("Path template contains '..' which may cause directory traversal")
    
    # Check for absolute paths in template variables (could be problematic)
    if re.search(r'\{[^}]+\}', template):
        # Template variables are OK, but warn if they might create absolute paths
        pass
    
    # Check for very long paths
    if len(template) > 500:
        warnings.append("Path template is very long (>500 chars), may cause issues")
    
    # Check for invalid characters that won't be in variables
    invalid_in_template = '<>:"|?*'
    for char in invalid_in_template:
        if char in template and f'{{{char}}}' not in template:
            warnings.append(f"Path template contains invalid character '{char}'")
    
    return len(warnings) == 0, warnings

