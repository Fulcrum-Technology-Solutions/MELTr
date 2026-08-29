"""Custom Jinja2 filters for templates."""

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Union
from zoneinfo import ZoneInfo

from jinja2 import Environment


class DateTimeWrapper:
    """Wrapper for datetime that supports addition with integers (seconds).

    This allows templates to use: {{ now() + 30 }} instead of {{ now() | add_seconds(30) }}
    """

    def __init__(self, dt: datetime) -> None:
        """Initialize wrapper with datetime object.

        Args:
            dt: Datetime object to wrap
        """
        self._dt = dt

    def __add__(self, other: int | float | timedelta) -> "DateTimeWrapper":
        """Add seconds (int/float) or timedelta to datetime.

        Args:
            other: Integer/float (treated as seconds) or timedelta

        Returns:
            New DateTimeWrapper with added time
        """
        if isinstance(other, (int, float)):
            return DateTimeWrapper(self._dt + timedelta(seconds=other))
        elif isinstance(other, timedelta):
            return DateTimeWrapper(self._dt + other)
        return NotImplemented

    def __sub__(
        self, other: int | float | timedelta | datetime
    ) -> Union["DateTimeWrapper", timedelta]:
        """Subtract seconds (int/float), timedelta, or datetime from datetime.

        Args:
            other: Integer/float (treated as seconds), timedelta, or datetime

        Returns:
            DateTimeWrapper if subtracting seconds/timedelta, timedelta if subtracting datetime
        """
        if isinstance(other, (int, float)):
            return DateTimeWrapper(self._dt - timedelta(seconds=other))
        elif isinstance(other, timedelta):
            return DateTimeWrapper(self._dt - other)
        elif isinstance(other, datetime):
            return self._dt - other
        elif isinstance(other, DateTimeWrapper):
            return self._dt - other._dt
        return NotImplemented

    def __mul__(self, other: int | float) -> "DateTimeWrapper":
        """Multiply datetime by integer/float (treats as seconds multiplier).

        Args:
            other: Integer/float multiplier (multiplies 1 second)

        Returns:
            New DateTimeWrapper with multiplied seconds added

        Example:
            {{ now() * 60 }}  # Adds 60 seconds (1 second * 60)
        """
        if isinstance(other, (int, float)):
            # Treat multiplication as: add (multiplier * 1 second)
            return DateTimeWrapper(self._dt + timedelta(seconds=other))
        return NotImplemented

    def __rmul__(self, other: int | float) -> "DateTimeWrapper":
        """Right multiplication (int * datetime).

        Args:
            other: Integer/float multiplier

        Returns:
            New DateTimeWrapper with multiplied seconds added
        """
        return self.__mul__(other)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to wrapped datetime object."""
        return getattr(self._dt, name)

    def __str__(self) -> str:
        """Return string representation of datetime."""
        return str(self._dt)

    def __repr__(self) -> str:
        """Return representation of wrapper."""
        return f"DateTimeWrapper({self._dt!r})"

    @property
    def datetime(self) -> datetime:
        """Get the wrapped datetime object."""
        return self._dt


def now(timezone: str | None = None) -> DateTimeWrapper:
    """Get current timestamp in specified timezone.

    Args:
        timezone: Timezone string (e.g., 'America/New_York'). Defaults to UTC.

    Returns:
        DateTimeWrapper with current datetime in specified timezone

    Example:
        {{ now() + 30 }}  # Add 30 seconds
        {{ now() - 3600 }}  # Subtract 1 hour
    """
    tz = ZoneInfo(timezone) if timezone else ZoneInfo("UTC")
    return DateTimeWrapper(datetime.now(tz))


def format_datetime(
    dt: datetime | DateTimeWrapper, format_str: str = "%Y-%m-%dT%H:%M:%S.%fZ"
) -> str:
    """Format datetime with strftime.

    Args:
        dt: Datetime object or DateTimeWrapper
        format_str: strftime format string

    Returns:
        Formatted datetime string
    """
    if isinstance(dt, DateTimeWrapper):
        dt = dt.datetime
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


def random_choice(choices: list[Any]) -> Any:
    """Choose random item from list.

    Args:
        choices: List of choices

    Returns:
        Randomly chosen item
    """
    if not choices:
        return None
    return random.choice(choices)


def random_weighted(choices: list[Any], weights: list[float]) -> Any:
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


def random_string(
    length: int, chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
) -> str:
    """Generate random string.

    Args:
        length: String length
        chars: Character set to use

    Returns:
        Random string
    """
    return "".join(random.choice(chars) for _ in range(length))


def random_public_ip() -> str:
    """Generate random public IP address.

    Returns:
        Random public IP address (not in private ranges)
    """
    # Generate IPs in ranges that are typically public
    # Avoiding 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    first_octet = random.choice(
        [
            random.randint(1, 9),
            random.randint(11, 126),
            random.randint(128, 171),
            random.randint(173, 191),
            random.randint(193, 223),
            random.randint(224, 239),  # Multicast (sometimes used)
        ]
    )
    return (
        f"{first_octet}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
    )


def random_private_ip() -> str:
    """Generate random private IP address.

    Returns:
        Random private IP address (RFC 1918 ranges)
    """
    range_type = random.choice(["10", "172", "192"])

    if range_type == "10":
        # 10.0.0.0/8
        return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    elif range_type == "172":
        # 172.16.0.0/12
        return f"172.{random.randint(16, 31)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    else:
        # 192.168.0.0/16
        return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"


def random_port(min_port: int | None = None, max_port: int | None = None) -> int:
    """Generate random port number.

    Args:
        min_port: Minimum port number (default: 1024)
        max_port: Maximum port number (default: 65535)

    Returns:
        Random port number in specified range

    Example:
        {{ random_port() }}  # Random port 1024-65535
        {{ random_port(1024, 65535) }}  # Explicit range
        {{ random_port(8000, 9000) }}  # Custom range
    """
    if min_port is None:
        min_port = 1024
    if max_port is None:
        max_port = 65535
    return random.randint(min_port, max_port)


def random_guid() -> str:
    """Generate random GUID/UUID.

    Returns:
        Random UUID string in standard format
    """
    return str(uuid.uuid4())


def timestamp_to_iso(dt: datetime | DateTimeWrapper) -> str:
    """Convert datetime to ISO 8601 format.

    Args:
        dt: Datetime object or DateTimeWrapper

    Returns:
        ISO 8601 formatted string (e.g., '2025-11-28T20:37:35.123456')
    """
    if isinstance(dt, DateTimeWrapper):
        dt = dt.datetime
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def random_hostname() -> str:
    """Generate random hostname.

    Returns:
        Random hostname in format: DESKTOP-XXXXX or LAPTOP-XXXXX or WIN-XXXXX
    """
    prefix = random.choice(["DESKTOP", "LAPTOP", "WIN", "SERVER", "PC", "WS", "SRV"])
    suffix = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(5))
    return f"{prefix}-{suffix}"


def iso8601(dt: datetime | DateTimeWrapper, include_microseconds: bool = True) -> str:
    """Format datetime as ISO 8601 (e.g., '2025-11-29T18:30:45.123456').

    Args:
        dt: Datetime object or DateTimeWrapper
        include_microseconds: Whether to include microseconds

    Returns:
        ISO 8601 formatted string
    """
    if isinstance(dt, DateTimeWrapper):
        dt = dt.datetime
    if isinstance(dt, datetime):
        if include_microseconds:
            return dt.isoformat()
        return dt.replace(microsecond=0).isoformat()
    return str(dt)


def iso8601_utc(dt: datetime | DateTimeWrapper, include_microseconds: bool = True) -> str:
    """Format datetime as ISO 8601 with UTC Z suffix (e.g., '2025-11-29T18:30:45.123456Z').

    Args:
        dt: Datetime object or DateTimeWrapper
        include_microseconds: Whether to include microseconds

    Returns:
        ISO 8601 formatted string with Z suffix
    """
    if isinstance(dt, DateTimeWrapper):
        dt = dt.datetime
    if isinstance(dt, datetime):
        # Convert to UTC if timezone-aware
        if dt.tzinfo:
            dt = dt.astimezone(ZoneInfo("UTC"))

        # Format with microseconds
        if include_microseconds:
            formatted = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
        else:
            formatted = dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Add Z suffix
        return formatted + "Z"
    return str(dt)


def rfc3339(dt: datetime | DateTimeWrapper) -> str:
    """Format datetime as RFC 3339 (ISO 8601 with timezone).

    Args:
        dt: Datetime object or DateTimeWrapper

    Returns:
        RFC 3339 formatted string
    """
    return iso8601(dt)


def unix_timestamp(dt: datetime | DateTimeWrapper) -> float:
    """Convert datetime to Unix timestamp.

    Args:
        dt: Datetime object or DateTimeWrapper

    Returns:
        Unix timestamp (seconds since epoch)
    """
    if isinstance(dt, DateTimeWrapper):
        dt = dt.datetime
    if isinstance(dt, datetime):
        return dt.timestamp()
    return 0.0


def add_seconds(dt: datetime | DateTimeWrapper, seconds: int) -> datetime | DateTimeWrapper:
    """Add seconds to a datetime object.

    Args:
        dt: Datetime object or DateTimeWrapper
        seconds: Number of seconds to add (can be negative)

    Returns:
        New datetime object or DateTimeWrapper with seconds added

    Example:
        {{ timestamp | add_seconds(30) }}
    """
    if isinstance(dt, DateTimeWrapper):
        return dt + seconds
    if isinstance(dt, datetime):
        return dt + timedelta(seconds=seconds)
    return dt


def subtract_seconds(dt: datetime | DateTimeWrapper, seconds: int) -> datetime | DateTimeWrapper:
    """Subtract seconds from a datetime object.

    Args:
        dt: Datetime object or DateTimeWrapper
        seconds: Number of seconds to subtract

    Returns:
        New datetime object or DateTimeWrapper with seconds subtracted

    Example:
        {{ timestamp | subtract_seconds(3600) }}
    """
    if isinstance(dt, DateTimeWrapper):
        return dt - seconds
    if isinstance(dt, datetime):
        return dt - timedelta(seconds=seconds)
    return dt


def random_hex(min_val: int, max_val: int) -> str:
    """Generate random hexadecimal value with '0x' prefix.

    Args:
        min_val: Minimum integer value
        max_val: Maximum integer value

    Returns:
        Hexadecimal string with '0x' prefix (e.g., '0x1a2b3c')

    Example:
        {{ random_hex(0, 67108864) }}  # Returns: "0x1a2b3c"
    """
    value = random.randint(min_val, max_val)
    return f"0x{format(value, 'x')}"


def register_filters(env: Environment) -> None:
    """Register custom filters with Jinja2 environment.

    Args:
        env: Jinja2 environment
    """
    # Datetime formatting filters
    env.filters["format_datetime"] = format_datetime
    env.filters["format_timestamp"] = format_datetime  # Alias for format_datetime
    env.filters["strftime"] = format_datetime  # Keep for backward compatibility
    env.filters["timestamp_to_iso"] = timestamp_to_iso
    env.filters["iso8601"] = iso8601
    env.filters["iso8601_utc"] = iso8601_utc
    env.filters["rfc3339"] = rfc3339
    env.filters["unix_timestamp"] = unix_timestamp
    env.filters["add_seconds"] = add_seconds
    env.filters["subtract_seconds"] = subtract_seconds

    # Random generation filters
    env.filters["random_int"] = random_int
    env.filters["random_choice"] = random_choice
    env.filters["random_string"] = random_string
    env.filters["random_weighted"] = random_weighted

    # Register as global functions (not just filters)
    env.globals["now"] = now
    env.globals["current_timestamp"] = now
    env.globals["random_int"] = random_int
    env.globals["random_choice"] = random_choice
    env.globals["random_string"] = random_string
    env.globals["random_weighted"] = random_weighted
    env.globals["random_public_ip"] = random_public_ip
    env.globals["random_private_ip"] = random_private_ip
    env.globals["random_port"] = random_port
    env.globals["random_guid"] = random_guid
    env.globals["random_hostname"] = random_hostname
    env.globals["random_hex"] = random_hex
    # Callable form: subtract_seconds(dt, n) / add_seconds(dt, n) (also available as filters)
    env.globals["add_seconds"] = add_seconds
    env.globals["subtract_seconds"] = subtract_seconds
