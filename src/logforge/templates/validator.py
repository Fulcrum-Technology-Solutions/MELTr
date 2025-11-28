"""Template validation logic."""

import ast
from pathlib import Path
from typing import List, Set

from jinja2 import Environment, Template, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

from logforge.templates.metadata import parse_metadata, TemplateMetadata
from logforge.utils.logging import get_logger

logger = get_logger(__name__)

# Unsafe operations to detect
UNSAFE_FUNCTIONS = {'eval', 'exec', 'compile', '__import__', 'open', 'file'}
UNSAFE_ATTRIBUTES = {'__class__', '__dict__', '__globals__', '__builtins__'}


class ValidationResult:
    """Result of template validation."""
    
    def __init__(self) -> None:
        """Initialize validation result."""
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_error(self, message: str) -> None:
        """Add validation error."""
        self.is_valid = False
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add validation warning."""
        self.warnings.append(message)


def validate_template(template_path: Path, metadata_path: Path) -> ValidationResult:
    """Validate a template and its metadata.
    
    Args:
        template_path: Path to template.j2 file
        metadata_path: Path to metadata.yaml file
        
    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()
    
    # Validate metadata
    try:
        metadata = parse_metadata(metadata_path)
        _validate_metadata_structure(metadata, metadata_path, result)
    except Exception as e:
        result.add_error(f"Metadata validation failed: {e}")
        return result  # Can't validate template without valid metadata
    
    # Validate template syntax
    try:
        with template_path.open('r', encoding='utf-8') as f:
            template_content = f.read()
        
        env = SandboxedEnvironment()
        template = env.parse(template_content)
        
        # Check for unsafe operations
        _check_template_safety(template_content, result)
        
        # Check registry function usage
        _validate_registry_functions(template_content, result)
        
    except TemplateSyntaxError as e:
        result.add_error(f"Template syntax error at line {e.lineno}: {e.message}")
    except Exception as e:
        result.add_error(f"Template validation failed: {e}")
    
    return result


def _validate_metadata_structure(metadata: TemplateMetadata, metadata_path: Path, result: ValidationResult) -> None:
    """Validate metadata structure matches directory."""
    # Extract vendor/product/data_source from path
    parts = metadata_path.parent.parts
    if len(parts) < 3:
        result.add_warning("Cannot verify metadata matches directory structure")
        return
    
    # Check if metadata matches directory structure
    # Path structure: .../vendor/product/data_source/template.meta.yaml
    data_source_from_path = parts[-2] if len(parts) >= 2 else None
    product_from_path = parts[-3] if len(parts) >= 3 else None
    vendor_from_path = parts[-4] if len(parts) >= 4 else None
    
    if vendor_from_path and metadata.vendor != vendor_from_path:
        result.add_warning(f"Metadata vendor '{metadata.vendor}' doesn't match directory '{vendor_from_path}'")
    
    if product_from_path and metadata.product != product_from_path:
        result.add_warning(f"Metadata product '{metadata.product}' doesn't match directory '{product_from_path}'")
    
    if data_source_from_path and metadata.data_source != data_source_from_path:
        result.add_warning(f"Metadata data_source '{metadata.data_source}' doesn't match directory '{data_source_from_path}'")


def _check_template_safety(template_content: str, result: ValidationResult) -> None:
    """Check template for unsafe operations."""
    # Check for unsafe function calls
    for func in UNSAFE_FUNCTIONS:
        if f'{func}(' in template_content:
            result.add_error(f"Unsafe function '{func}' detected in template")
    
    # Check for unsafe attribute access
    for attr in UNSAFE_ATTRIBUTES:
        if f'.{attr}' in template_content or f'[{attr!r}]' in template_content:
            result.add_error(f"Unsafe attribute access '{attr}' detected in template")


def _validate_registry_functions(template_content: str, result: ValidationResult) -> None:
    """Validate registry function calls in template."""
    valid_registry_functions = {
        'get_random_user',
        'get_random_device',
        'get_random_service',
        'get_user',
        'get_device',
        'get_service',
        'get_organization',
        'get_organization_field',
        'get_organization_contact',
    }
    
    # Simple check for registry.* calls
    import re
    registry_calls = re.findall(r'registry\.(\w+)', template_content)
    
    for func_name in registry_calls:
        if func_name not in valid_registry_functions:
            result.add_warning(f"Unknown registry function: registry.{func_name}")

