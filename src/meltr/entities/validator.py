"""Entity validation logic."""

import ipaddress
import json
import re
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft7Validator, ValidationError

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    # Type stub for when jsonschema is not available
    Draft7Validator = None  # type: ignore
    ValidationError = Exception  # type: ignore

from meltr.utils.logging import get_logger

logger = get_logger(__name__)

# Email validation regex (simplified)
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# MAC address validation regex
MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

# Cache for schema validator
_SCHEMA_VALIDATOR: Any | None = None


def _find_schema_path(schema_path: Path | None = None) -> Path:
    """Find path to entity schema file.

    Searches in multiple locations:
    1. Explicitly provided schema_path
    2. Current working directory (schemas/entity.schema.json)
    3. Package location (schemas/entity.schema.json relative to package)
    4. Parent directories up to 5 levels (for nested project structures)

    Args:
        schema_path: Optional explicit path to schema file

    Returns:
        Path to entity.schema.json

    Raises:
        FileNotFoundError: If schema file cannot be found
    """
    # If explicit path provided, use it
    if schema_path is not None:
        if schema_path.exists():
            return schema_path.resolve()
        raise FileNotFoundError(f"Schema file not found at provided path: {schema_path}")

    # Try current working directory
    cwd_schema = Path.cwd() / "schemas" / "entity.schema.json"
    if cwd_schema.exists():
        return cwd_schema.resolve()

    # Try package location (for installed packages)
    package_dir = Path(__file__).parent.parent.parent.parent
    package_schema = package_dir / "schemas" / "entity.schema.json"
    if package_schema.exists():
        return package_schema.resolve()

    # Try parent directories (for nested project structures)
    current = Path.cwd()
    for _ in range(5):  # Search up to 5 levels up
        parent_schema = current / "schemas" / "entity.schema.json"
        if parent_schema.exists():
            return parent_schema.resolve()
        if current == current.parent:  # Reached filesystem root
            break
        current = current.parent

    # Try relative to the file being validated (if we have context)
    # This is a fallback that won't work without context, but included for completeness

    raise FileNotFoundError(
        "Entity schema file not found. Searched in:\n"
        f"  - {Path.cwd() / 'schemas' / 'entity.schema.json'}\n"
        f"  - {package_dir / 'schemas' / 'entity.schema.json'}\n"
        "  - Parent directories (up to 5 levels)\n"
        "\n"
        "You can specify the schema path explicitly or ensure schemas/entity.schema.json exists."
    )


def _load_schema_validator(schema_path: Path | None = None) -> Any:
    """Load and cache the entity schema validator.

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
            with found_schema_path.open("r", encoding="utf-8") as f:
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


def _validate_entities_structure(data: dict[str, Any]) -> None:
    """Validate entity structure only (allows empty lists).

    Args:
        data: Entity data dictionary

    Raises:
        ValueError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Entities data must be a dictionary")

    # Validate organization (required)
    if "organization" not in data:
        raise ValueError("Missing required 'organization' section")

    org = data["organization"]
    if not isinstance(org, dict):
        raise ValueError("'organization' must be a dictionary")

    if "name" not in org:
        raise ValueError("'organization.name' is required")
    if "domain" not in org:
        raise ValueError("'organization.domain' is required")

    # Check sections exist (but allow empty lists)
    for section in ["users", "devices", "services"]:
        if section not in data:
            raise ValueError(f"Missing required '{section}' section")
        if not isinstance(data[section], list):
            raise ValueError(f"'{section}' must be a list")


def validate_entities(data: dict[str, Any], schema_path: Path | None = None) -> None:
    """Validate entity registry data structure.

    Uses JSON schema validation for structure and format validation,
    then performs additional business logic checks (uniqueness, etc.).

    Args:
        data: Entity data dictionary
        schema_path: Optional path to entity.schema.json. If None, searches automatically.

    Raises:
        ValueError: If validation fails
    """
    # First, validate against JSON schema if available
    schema_validation_used = False
    if JSONSCHEMA_AVAILABLE:
        try:
            validator = _load_schema_validator(schema_path)
            errors = list(validator.iter_errors(data))
            if errors:
                # Format schema errors into user-friendly messages
                error_messages = []
                for error in sorted(errors, key=lambda e: e.path):
                    location = "/".join(str(p) for p in error.absolute_path) or "<root>"
                    error_messages.append(f"{location}: {error.message}")

                raise ValueError(
                    "Entity schema validation failed:\n"
                    + "\n".join(f"  - {msg}" for msg in error_messages)
                )
            schema_validation_used = True
        except RuntimeError as e:
            # Schema not available or not found - log warning but continue with programmatic validation
            logger.warning(
                f"JSON schema validation unavailable: {e}. Using programmatic validation only."
            )
        except Exception as e:
            # Handle ValidationError or any other exception
            if hasattr(e, "message"):
                raise ValueError(f"Entity schema validation failed: {e.message}") from e
            raise ValueError(f"Entity schema validation failed: {e}") from e

    # If schema validation wasn't used, do basic structure validation
    if not schema_validation_used:
        _validate_basic_structure(data)

    # Additional business logic validation that JSON schema can't handle:
    # 1. Uniqueness checks (case-insensitive for usernames/emails)
    # 2. Network range start_ip < end_ip validation

    # Validate users uniqueness
    users = data.get("users", [])
    usernames = set()
    emails = set()
    for i, user in enumerate(users):
        _validate_user_uniqueness(user, i, usernames, emails)

    # Validate devices uniqueness
    devices = data.get("devices", [])
    hostnames = set()
    for i, device in enumerate(devices):
        _validate_device_uniqueness(device, i, hostnames)

    # Validate services uniqueness
    services = data.get("services", [])
    service_names = set()
    for i, service in enumerate(services):
        _validate_service_uniqueness(service, i, service_names)

    # Validate network_ranges business logic (start_ip < end_ip)
    if "network_ranges" in data:
        network_ranges = data["network_ranges"]
        for i, range_def in enumerate(network_ranges):
            _validate_network_range_logic(range_def, i)


def _validate_basic_structure(data: dict[str, Any]) -> None:
    """Validate basic entity structure (fallback when JSON schema unavailable).

    Args:
        data: Entity data dictionary

    Raises:
        ValueError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Entities data must be a dictionary")

    # Validate organization (required)
    if "organization" not in data:
        raise ValueError("Missing required 'organization' section")

    org = data["organization"]
    if not isinstance(org, dict):
        raise ValueError("'organization' must be a dictionary")

    if "name" not in org:
        raise ValueError("'organization.name' is required")
    if "domain" not in org:
        raise ValueError("'organization.domain' is required")

    # Validate users (required, min 1)
    if "users" not in data:
        raise ValueError("Missing required 'users' section")

    users = data["users"]
    if not isinstance(users, list):
        raise ValueError("'users' must be a list")

    if len(users) == 0:
        raise ValueError("'users' list must contain at least one user")

    # Validate each user has required fields
    for i, user in enumerate(users):
        if not isinstance(user, dict):
            raise ValueError(f"User at index {i} must be a dictionary")
        for field in ["username", "email", "full_name"]:
            if field not in user:
                raise ValueError(f"User at index {i} missing required field: {field}")

    # Validate devices (required, min 1)
    if "devices" not in data:
        raise ValueError("Missing required 'devices' section")

    devices = data["devices"]
    if not isinstance(devices, list):
        raise ValueError("'devices' must be a list")

    if len(devices) == 0:
        raise ValueError("'devices' list must contain at least one device")

    # Validate each device has required fields
    for i, device in enumerate(devices):
        if not isinstance(device, dict):
            raise ValueError(f"Device at index {i} must be a dictionary")
        for field in ["hostname", "ip_address", "mac_address"]:
            if field not in device:
                raise ValueError(f"Device at index {i} missing required field: {field}")

    # Validate services (required, min 1)
    if "services" not in data:
        raise ValueError("Missing required 'services' section")

    services = data["services"]
    if not isinstance(services, list):
        raise ValueError("'services' must be a list")

    if len(services) == 0:
        raise ValueError("'services' list must contain at least one service")

    # Validate each service has required fields
    for i, service in enumerate(services):
        if not isinstance(service, dict):
            raise ValueError(f"Service at index {i} must be a dictionary")
        for field in ["name", "port", "protocol"]:
            if field not in service:
                raise ValueError(f"Service at index {i} missing required field: {field}")


def _validate_user_uniqueness(
    user: dict[str, Any], index: int, usernames: set, emails: set
) -> None:
    """Validate user uniqueness (usernames and emails must be unique, case-insensitive).

    Note: Structure and format validation is handled by JSON schema.

    Args:
        user: User entity dictionary
        index: Index of user in array (for error messages)
        usernames: Set of lowercase usernames seen so far
        emails: Set of lowercase emails seen so far

    Raises:
        ValueError: If uniqueness constraint violated
    """
    username = user.get("username", "")
    email = user.get("email", "")

    # Check username uniqueness (case-insensitive)
    if username:
        username_lower = username.lower()
        if username_lower in usernames:
            raise ValueError(f"User at index {index}: duplicate username '{username}'")
        usernames.add(username_lower)

    # Check email uniqueness (case-insensitive)
    if email:
        email_lower = email.lower()
        if email_lower in emails:
            raise ValueError(f"User at index {index}: duplicate email '{email}'")
        emails.add(email_lower)


def _validate_device_uniqueness(device: dict[str, Any], index: int, hostnames: set) -> None:
    """Validate device uniqueness (hostnames must be unique).

    Note: Structure and format validation is handled by JSON schema.

    Args:
        device: Device entity dictionary
        index: Index of device in array (for error messages)
        hostnames: Set of hostnames seen so far

    Raises:
        ValueError: If uniqueness constraint violated
    """
    hostname = device.get("hostname", "")

    # Check hostname uniqueness
    if hostname:
        if hostname in hostnames:
            raise ValueError(f"Device at index {index}: duplicate hostname '{hostname}'")
        hostnames.add(hostname)


def _validate_service_uniqueness(service: dict[str, Any], index: int, service_names: set) -> None:
    """Validate service uniqueness (service names must be unique).

    Note: Structure and format validation is handled by JSON schema.

    Args:
        service: Service entity dictionary
        index: Index of service in array (for error messages)
        service_names: Set of service names seen so far

    Raises:
        ValueError: If uniqueness constraint violated
    """
    name = service.get("name", "")

    # Check service name uniqueness
    if name:
        if name in service_names:
            raise ValueError(f"Service at index {index}: duplicate service name '{name}'")
        service_names.add(name)


def _validate_network_range_logic(range_def: dict[str, Any], index: int) -> None:
    """Validate network range business logic (start_ip < end_ip).

    Note: Structure and format validation is handled by JSON schema.

    Args:
        range_def: Network range definition dictionary
        index: Index of range in array (for error messages)

    Raises:
        ValueError: If business logic constraint violated
    """
    # JSON schema validates that either cidr OR start_ip+end_ip exists
    # Here we only need to validate the business logic: start_ip < end_ip
    if "start_ip" in range_def and "end_ip" in range_def:
        start_ip = range_def["start_ip"]
        end_ip = range_def["end_ip"]
        try:
            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)
            if start >= end:
                raise ValueError(
                    f"Network range at index {index}: start_ip ({start_ip}) must be less than end_ip ({end_ip})"
                )
        except ValueError as e:
            # This should be caught by JSON schema, but handle it here too for safety
            raise ValueError(f"Network range at index {index}: invalid IP addresses: {e}") from e
