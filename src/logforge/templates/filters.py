"""Custom Jinja2 filters for templates."""

import random
import uuid
from datetime import datetime, timedelta
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


def random_weighted(choices: List[Any], weights: List[float]) -> Any:
    """Choose random item from list based on weights.
    
    Args:
        choices: List of choices
        weights: List of weights (probabilities) corresponding to each choice
        
    Returns:
        Randomly chosen item based on weighted probabilities
        
    Example:
        ['true', 'false'] | random_weighted([90, 10])  # 90% 'true', 10% 'false'
    """
    if not choices or not weights:
        return None
    
    if len(choices) != len(weights):
        # If weights don't match, use equal weights
        return random.choice(choices)
    
    # Normalize weights to sum to 1.0
    total_weight = sum(weights)
    if total_weight == 0:
        return random.choice(choices)
    
    normalized_weights = [w / total_weight for w in weights]
    
    # Use random.choices with normalized weights
    return random.choices(choices, weights=normalized_weights, k=1)[0]


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


def iso8601(dt: datetime, include_microseconds: bool = True) -> str:
    """Format datetime as ISO 8601 (e.g., '2025-11-29T18:30:45.123456').
    
    Args:
        dt: Datetime object
        include_microseconds: Whether to include microseconds
        
    Returns:
        ISO 8601 formatted string
    """
    if isinstance(dt, datetime):
        if include_microseconds:
            return dt.isoformat()
        return dt.replace(microsecond=0).isoformat()
    return str(dt)


def iso8601_utc(dt: datetime, include_microseconds: bool = True) -> str:
    """Format datetime as ISO 8601 with UTC Z suffix (e.g., '2025-11-29T18:30:45.123456Z').
    
    Args:
        dt: Datetime object
        include_microseconds: Whether to include microseconds
        
    Returns:
        ISO 8601 formatted string with Z suffix
    """
    if isinstance(dt, datetime):
        # Convert to UTC if timezone-aware
        if dt.tzinfo:
            dt = dt.astimezone(ZoneInfo('UTC'))
        
        # Format with microseconds
        if include_microseconds:
            formatted = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        else:
            formatted = dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Add Z suffix
        return formatted + 'Z'
    return str(dt)


def rfc3339(dt: datetime) -> str:
    """Format datetime as RFC 3339 (ISO 8601 with timezone).
    
    Args:
        dt: Datetime object
        
    Returns:
        RFC 3339 formatted string
    """
    return iso8601(dt)


def unix_timestamp(dt: datetime) -> float:
    """Convert datetime to Unix timestamp.
    
    Args:
        dt: Datetime object
        
    Returns:
        Unix timestamp (seconds since epoch)
    """
    if isinstance(dt, datetime):
        return dt.timestamp()
    return 0.0


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """Add seconds to a datetime object.
    
    Args:
        dt: Datetime object
        seconds: Number of seconds to add (can be negative)
        
    Returns:
        New datetime object with seconds added
        
    Example:
        {{ timestamp | add_seconds(30) }}
    """
    if isinstance(dt, datetime):
        return dt + timedelta(seconds=seconds)
    return dt


def subtract_seconds(dt: datetime, seconds: int) -> datetime:
    """Subtract seconds from a datetime object.
    
    Args:
        dt: Datetime object
        seconds: Number of seconds to subtract
        
    Returns:
        New datetime object with seconds subtracted
        
    Example:
        {{ timestamp | subtract_seconds(3600) }}
    """
    if isinstance(dt, datetime):
        return dt - timedelta(seconds=seconds)
    return dt


def register_filters(env: Environment) -> None:
    """Register custom filters with Jinja2 environment.
    
    Args:
        env: Jinja2 environment
    """
    # Datetime formatting filters
    env.filters['format_datetime'] = format_datetime
    env.filters['format_timestamp'] = format_datetime  # Alias for format_datetime
    env.filters['strftime'] = format_datetime  # Keep for backward compatibility
    env.filters['timestamp_to_iso'] = timestamp_to_iso
    env.filters['iso8601'] = iso8601
    env.filters['iso8601_utc'] = iso8601_utc
    env.filters['rfc3339'] = rfc3339
    env.filters['unix_timestamp'] = unix_timestamp
    env.filters['add_seconds'] = add_seconds
    env.filters['subtract_seconds'] = subtract_seconds
    
    # Random generation filters
    env.filters['random_int'] = random_int
    env.filters['random_choice'] = random_choice
    env.filters['random_string'] = random_string
    env.filters['random_weighted'] = random_weighted
    
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

