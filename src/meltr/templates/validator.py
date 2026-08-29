"""Template validation logic."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    Draft7Validator = None  # type: ignore
    ValidationError = Exception  # type: ignore

from meltr.templates.metadata import parse_metadata, TemplateMetadata
from meltr.utils.logging import get_logger

logger = get_logger(__name__)

# Cache for schema validator
_SCHEMA_VALIDATOR: Optional[Any] = None

# Unsafe operations to detect
UNSAFE_FUNCTIONS = {'eval', 'exec', 'compile', '__import__', 'open', 'file'}
UNSAFE_ATTRIBUTES = {'__class__', '__dict__', '__globals__', '__builtins__'}


def _find_schema_path(schema_path: Optional[Path] = None) -> Path:
    """Find path to template schema file.
    
    Searches in multiple locations:
    1. Explicitly provided schema_path
    2. Current working directory (schemas/template.schema.json)
    3. Package location (schemas/template.schema.json relative to package)
    4. Parent directories up to 5 levels (for nested project structures)
    
    Args:
        schema_path: Optional explicit path to schema file
        
    Returns:
        Path to template.schema.json
        
    Raises:
        FileNotFoundError: If schema file cannot be found
    """
    # If explicit path provided, use it
    if schema_path is not None:
        if schema_path.exists():
            return schema_path.resolve()
        raise FileNotFoundError(f"Schema file not found at provided path: {schema_path}")
    
    # Try current working directory
    cwd_schema = Path.cwd() / 'schemas' / 'template.schema.json'
    if cwd_schema.exists():
        return cwd_schema.resolve()
    
    # Try package location (for installed packages)
    package_dir = Path(__file__).parent.parent.parent.parent
    package_schema = package_dir / 'schemas' / 'template.schema.json'
    if package_schema.exists():
        return package_schema.resolve()
    
    # Try parent directories (for nested project structures)
    current = Path.cwd()
    for _ in range(5):  # Search up to 5 levels up
        parent_schema = current / 'schemas' / 'template.schema.json'
        if parent_schema.exists():
            return parent_schema.resolve()
        if current == current.parent:  # Reached filesystem root
            break
        current = current.parent
    
    raise FileNotFoundError(
        "Template schema file not found. Searched in:\n"
        f"  - {Path.cwd() / 'schemas' / 'template.schema.json'}\n"
        f"  - {package_dir / 'schemas' / 'template.schema.json'}\n"
        "  - Parent directories (up to 5 levels)\n"
        "\n"
        "You can specify the schema path explicitly or ensure schemas/template.schema.json exists."
    )


def _load_schema_validator(schema_path: Optional[Path] = None) -> Any:
    """Load and cache the template schema validator.
    
    Args:
        schema_path: Optional explicit path to schema file. If None, searches automatically.
    
    Returns:
        Draft7Validator instance
        
    Raises:
        RuntimeError: If jsonschema is not available or schema file not found
    """
    global _SCHEMA_VALIDATOR
    
    if not JSONSCHEMA_AVAILABLE:
        raise RuntimeError(
            "jsonschema package is required for schema validation. "
            "Install with: pip install jsonschema"
        )
    
    # Use cached validator if available and no explicit path provided
    if _SCHEMA_VALIDATOR is None or schema_path is not None:
        try:
            found_schema_path = _find_schema_path(schema_path)
        except FileNotFoundError as e:
            raise RuntimeError(str(e)) from e
        
        try:
            with found_schema_path.open('r', encoding='utf-8') as f:
                schema_data = json.load(f)
            validator = Draft7Validator(schema_data)
            
            # Only cache if using default path
            if schema_path is None:
                _SCHEMA_VALIDATOR = validator
            
            return validator
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in schema file {found_schema_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load schema from {found_schema_path}: {e}") from e
    
    return _SCHEMA_VALIDATOR


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


def _validate_metadata_schema(metadata_data: Dict[str, Any], result: ValidationResult) -> None:
    """Validate metadata against JSON schema.
    
    Args:
        metadata_data: Parsed metadata dictionary
        result: ValidationResult to add errors/warnings to
    """
    if not JSONSCHEMA_AVAILABLE:
        result.add_warning(
            "JSON schema validation skipped (jsonschema not available). "
            "Install with: pip install jsonschema for full validation."
        )
        return
    
    try:
        validator = _load_schema_validator()
        errors = list(validator.iter_errors(metadata_data))
        
        if errors:
            # Format schema errors into user-friendly messages
            for error in sorted(errors, key=lambda e: e.path):
                location = "/".join(str(p) for p in error.absolute_path) or "<root>"
                result.add_error(f"Schema validation error at {location}: {error.message}")
    except RuntimeError as e:
        # Schema not available or not found - log warning but continue with Pydantic validation
        result.add_warning(f"JSON schema validation skipped: {e}")
    except Exception as e:
        result.add_warning(f"JSON schema validation failed: {e}")


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
        # Load raw YAML data for schema validation
        with metadata_path.open('r', encoding='utf-8') as f:
            metadata_yaml_data = yaml.safe_load(f)
        
        if not isinstance(metadata_yaml_data, dict):
            result.add_error("Metadata file must contain a YAML mapping/object")
            return result
        
        # Validate against JSON schema first
        _validate_metadata_schema(metadata_yaml_data, result)
        
        # Then parse with Pydantic for type validation
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









