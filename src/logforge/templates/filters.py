"""Custom Jinja2 filters for templates."""

import random
import uuid
from datetime import datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from jinja2 import Environment


def now(timezone: Optional[str] = None) -> datetime:
    """Get current timestamp in specified timezone.
    
    Args:
        timezone: Timezone string (e.g., 'America/New_York'). Defaults to UTC.
    
    Returns:
        Current datetime object in specified timezone
    """
    tz = ZoneInfo(timezone) if timezone else ZoneInfo('UTC')
    return datetime.now(tz)


def format_datetime(dt: datetime, format_str: str = '%Y-%m-%dT%H:%M:%S.%fZ') -> str:
    """Format datetime with strftime.
    
    Args:
        dt: Datetime object
        format_str: strftime format string
        
    Returns:
        Formatted datetime string
    """
    if isinstance(dt, datetime):
        return dt.strftime(format_str)
    return str(dt)


def random_int(min_val: int, max_val: int) -> int:
    """Generate random integer in range.
    
    Args:
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Random integer
    """
    return random.randint(min_val, max_val)


def random_choice(choices: List[Any]) -> Any:
    """Choose random item from list.
    
    Args:
        choices: List of choices
        
    Returns:
        Randomly chosen item
    """
    if not choices:
        return None
    return random.choice(choices)


def random_string(length: int, chars: str = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') -> str:
    """Generate random string.
    
    Args:
        length: String length
        chars: Character set to use
        
    Returns:
        Random string
    """
    return ''.join(random.choice(chars) for _ in range(length))


def random_public_ip() -> str:
    """Generate random public IP address.
    
    Returns:
        Random public IP address (not in private ranges)
    """
    # Generate IPs in ranges that are typically public
    # Avoiding 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    first_octet = random.choice([
        random.randint(1, 9),
        random.randint(11, 126),
        random.randint(128, 171),
        random.randint(173, 191),
        random.randint(193, 223),
        random.randint(224, 239),  # Multicast (sometimes used)
    ])
    return f"{first_octet}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"


def random_private_ip() -> str:
    """Generate random private IP address.
    
    Returns:
        Random private IP address (RFC 1918 ranges)
    """
    range_type = random.choice(['10', '172', '192'])
    
    if range_type == '10':
        # 10.0.0.0/8
        return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    elif range_type == '172':
        # 172.16.0.0/12
        return f"172.{random.randint(16, 31)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    else:
        # 192.168.0.0/16
        return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"


def random_port() -> int:
    """Generate random port number.
    
    Returns:
        Random port number (1024-65535)
    """
    return random.randint(1024, 65535)


def random_guid() -> str:
    """Generate random GUID/UUID.
    
    Returns:
        Random UUID string in standard format
    """
    return str(uuid.uuid4())


def timestamp_to_iso(dt: datetime) -> str:
    """Convert datetime to ISO 8601 format.
    
    Args:
        dt: Datetime object
        
    Returns:
        ISO 8601 formatted string (e.g., '2025-11-28T20:37:35.123456')
    """
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def random_hostname() -> str:
    """Generate random hostname.
    
    Returns:
        Random hostname in format: DESKTOP-XXXXX or LAPTOP-XXXXX or WIN-XXXXX
    """
    prefix = random.choice(['DESKTOP', 'LAPTOP', 'WIN', 'SERVER', 'PC', 'WS', 'SRV'])
    suffix = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(5))
    return f"{prefix}-{suffix}"


def register_filters(env: Environment) -> None:
    """Register custom filters with Jinja2 environment.
    
    Args:
        env: Jinja2 environment
    """
    env.filters['format_datetime'] = format_datetime
    env.filters['format_timestamp'] = format_datetime  # Alias for format_datetime
    env.filters['timestamp_to_iso'] = timestamp_to_iso
    env.filters['random_int'] = random_int
    env.filters['random_choice'] = random_choice
    env.filters['random_string'] = random_string
    
    # Register as global functions (not just filters)
    env.globals['now'] = now
    env.globals['current_timestamp'] = now
    env.globals['random_int'] = random_int
    env.globals['random_choice'] = random_choice
    env.globals['random_string'] = random_string
    env.globals['random_public_ip'] = random_public_ip
    env.globals['random_private_ip'] = random_private_ip
    env.globals['random_port'] = random_port
    env.globals['random_guid'] = random_guid
    env.globals['random_hostname'] = random_hostname

