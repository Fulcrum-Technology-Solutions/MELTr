"""Entity validation logic."""

import ipaddress
import re
from typing import Any, Dict, List

from logforge.utils.logging import get_logger

logger = get_logger(__name__)

# Email validation regex (simplified)
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# MAC address validation regex
MAC_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')


def _validate_entities_structure(data: Dict[str, Any]) -> None:
    """Validate entity structure only (allows empty lists).
    
    Args:
        data: Entity data dictionary
        
    Raises:
        ValueError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Entities data must be a dictionary")
    
    # Validate organization (required)
    if 'organization' not in data:
        raise ValueError("Missing required 'organization' section")
    
    org = data['organization']
    if not isinstance(org, dict):
        raise ValueError("'organization' must be a dictionary")
    
    if 'name' not in org:
        raise ValueError("'organization.name' is required")
    if 'domain' not in org:
        raise ValueError("'organization.domain' is required")
    
    # Check sections exist (but allow empty lists)
    for section in ['users', 'devices', 'services']:
        if section not in data:
            raise ValueError(f"Missing required '{section}' section")
        if not isinstance(data[section], list):
            raise ValueError(f"'{section}' must be a list")


def validate_entities(data: Dict[str, Any]) -> None:
    """Validate entity registry data structure.
    
    Args:
        data: Entity data dictionary
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValueError("Entities data must be a dictionary")
    
    # Validate organization (required)
    if 'organization' not in data:
        raise ValueError("Missing required 'organization' section")
    
    org = data['organization']
    if not isinstance(org, dict):
        raise ValueError("'organization' must be a dictionary")
    
    if 'name' not in org:
        raise ValueError("'organization.name' is required")
    if 'domain' not in org:
        raise ValueError("'organization.domain' is required")
    
    # Validate domain format (basic check)
    domain = org['domain']
    if not isinstance(domain, str) or len(domain) < 1:
        raise ValueError("'organization.domain' must be a non-empty string")
    
    # Validate users (required, min 1)
    if 'users' not in data:
        raise ValueError("Missing required 'users' section")
    
    users = data['users']
    if not isinstance(users, list):
        raise ValueError("'users' must be a list")
    
    if len(users) == 0:
        raise ValueError("'users' list must contain at least one user")
    
    # Validate each user
    usernames = set()
    emails = set()
    for i, user in enumerate(users):
        _validate_user(user, i, usernames, emails)
    
    # Validate devices (required)
    if 'devices' not in data:
        raise ValueError("Missing required 'devices' section")
    
    devices = data['devices']
    if not isinstance(devices, list):
        raise ValueError("'devices' must be a list")
    
    # Validate each device
    hostnames = set()
    for i, device in enumerate(devices):
        _validate_device(device, i, hostnames)
    
    # Validate services (required)
    if 'services' not in data:
        raise ValueError("Missing required 'services' section")
    
    # Validate services (required, min 1)
    if 'services' not in data:
        raise ValueError("Missing required 'services' section")
    
    services = data['services']
    if not isinstance(services, list):
        raise ValueError("'services' must be a list")
    
    if len(services) == 0:
        raise ValueError("'services' list must contain at least one service")
    
    # Validate each service
    service_names = set()
    for i, service in enumerate(services):
        _validate_service(service, i, service_names)
    
    # Validate network_ranges if present (optional)
    if 'network_ranges' in data:
        network_ranges = data['network_ranges']
        if not isinstance(network_ranges, list):
            raise ValueError("'network_ranges' must be a list")
        for i, range_def in enumerate(network_ranges):
            _validate_network_range(range_def, i)


def _validate_user(user: Dict[str, Any], index: int, usernames: set, emails: set) -> None:
    """Validate a user entity."""
    if not isinstance(user, dict):
        raise ValueError(f"User at index {index} must be a dictionary")
    
    # Required fields
    for field in ['username', 'email', 'full_name']:
        if field not in user:
            raise ValueError(f"User at index {index} missing required field: {field}")
    
    username = user['username']
    if not isinstance(username, str) or len(username) == 0:
        raise ValueError(f"User at index {index}: 'username' must be a non-empty string")
    
    # Check uniqueness (case-insensitive)
    username_lower = username.lower()
    if username_lower in usernames:
        raise ValueError(f"User at index {index}: duplicate username '{username}'")
    usernames.add(username_lower)
    
    # Validate email
    email = user['email']
    if not isinstance(email, str):
        raise ValueError(f"User at index {index}: 'email' must be a string")
    
    if not EMAIL_PATTERN.match(email):
        raise ValueError(f"User at index {index}: invalid email format '{email}'")
    
    # Check email uniqueness (case-insensitive)
    email_lower = email.lower()
    if email_lower in emails:
        raise ValueError(f"User at index {index}: duplicate email '{email}'")
    emails.add(email_lower)


def _validate_device(device: Dict[str, Any], index: int, hostnames: set) -> None:
    """Validate a device entity."""
    if not isinstance(device, dict):
        raise ValueError(f"Device at index {index} must be a dictionary")
    
    # Required fields
    for field in ['hostname', 'ip_address', 'mac_address']:
        if field not in device:
            raise ValueError(f"Device at index {index} missing required field: {field}")
    
    hostname = device['hostname']
    if not isinstance(hostname, str) or len(hostname) == 0:
        raise ValueError(f"Device at index {index}: 'hostname' must be a non-empty string")
    
    # Check uniqueness
    if hostname in hostnames:
        raise ValueError(f"Device at index {index}: duplicate hostname '{hostname}'")
    hostnames.add(hostname)
    
    # Validate IP address
    ip_address = device['ip_address']
    if not isinstance(ip_address, str):
        raise ValueError(f"Device at index {index}: 'ip_address' must be a string")
    
    try:
        ipaddress.ip_address(ip_address)
    except ValueError:
        raise ValueError(f"Device at index {index}: invalid IP address '{ip_address}'")
    
    # Validate MAC address
    mac_address = device['mac_address']
    if not isinstance(mac_address, str):
        raise ValueError(f"Device at index {index}: 'mac_address' must be a string")
    
    if not MAC_PATTERN.match(mac_address):
        raise ValueError(f"Device at index {index}: invalid MAC address format '{mac_address}'")


def _validate_service(service: Dict[str, Any], index: int, service_names: set) -> None:
    """Validate a service entity."""
    if not isinstance(service, dict):
        raise ValueError(f"Service at index {index} must be a dictionary")
    
    # Required fields
    for field in ['name', 'port', 'protocol']:
        if field not in service:
            raise ValueError(f"Service at index {index} missing required field: {field}")
    
    name = service['name']
    if not isinstance(name, str) or len(name) == 0:
        raise ValueError(f"Service at index {index}: 'name' must be a non-empty string")
    
    # Check uniqueness
    if name in service_names:
        raise ValueError(f"Service at index {index}: duplicate service name '{name}'")
    service_names.add(name)
    
    # Validate port
    port = service['port']
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"Service at index {index}: 'port' must be an integer between 1 and 65535")
    
    # Validate protocol
    protocol = service['protocol']
    if not isinstance(protocol, str) or len(protocol) == 0:
        raise ValueError(f"Service at index {index}: 'protocol' must be a non-empty string")


def _validate_network_range(range_def: Dict[str, Any], index: int) -> None:
    """Validate a network range definition."""
    if not isinstance(range_def, dict):
        raise ValueError(f"Network range at index {index} must be a dictionary")
    
    has_cidr = 'cidr' in range_def
    has_start_end = 'start_ip' in range_def and 'end_ip' in range_def
    
    if not (has_cidr or has_start_end):
        raise ValueError(f"Network range at index {index} must have either 'cidr' or both 'start_ip' and 'end_ip'")
    
    if has_cidr:
        cidr = range_def['cidr']
        if not isinstance(cidr, str):
            raise ValueError(f"Network range at index {index}: 'cidr' must be a string")
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            raise ValueError(f"Network range at index {index}: invalid CIDR '{cidr}'")
    
    if has_start_end:
        start_ip = range_def['start_ip']
        end_ip = range_def['end_ip']
        try:
            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)
            if start >= end:
                raise ValueError(f"Network range at index {index}: start_ip must be less than end_ip")
        except ValueError as e:
            raise ValueError(f"Network range at index {index}: invalid IP addresses: {e}")
