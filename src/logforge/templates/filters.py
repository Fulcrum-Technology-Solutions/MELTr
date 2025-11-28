"""Custom Jinja2 filters for templates."""

import random
from datetime import datetime
from typing import Any, List

from jinja2 import Environment


def now() -> datetime:
    """Get current timestamp.
    
    Returns:
        Current datetime object
    """
    return datetime.utcnow()


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


def register_filters(env: Environment) -> None:
    """Register custom filters with Jinja2 environment.
    
    Args:
        env: Jinja2 environment
    """
    env.filters['format_datetime'] = format_datetime
    env.filters['random_int'] = random_int
    env.filters['random_choice'] = random_choice
    env.filters['random_string'] = random_string
    
    # Register as global functions (not just filters)
    env.globals['now'] = now
    env.globals['current_timestamp'] = now
    env.globals['random_int'] = random_int
    env.globals['random_choice'] = random_choice
    env.globals['random_string'] = random_string

