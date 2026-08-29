"""Frequency calculation logic for generators."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from meltr.core.config import FrequencyConfig
from meltr.templates.metadata import TemplateMetadata


def calculate_rate(frequency_config: FrequencyConfig) -> float:
    """Calculate current event rate based on time and day.

    Args:
        frequency_config: Frequency configuration

    Returns:
        Current rate in events per second
    """
    base_rate = frequency_config.base_rate

    # If no variations, return base rate
    if not frequency_config.variation:
        return base_rate

    # Get current time and day
    now = datetime.now()
    current_day = now.isoweekday()  # 1=Monday, 7=Sunday
    current_time = now.time()

    # Find matching variation rule
    multiplier = 1.0

    for variation in frequency_config.variation:
        matches = True

        # Check day match
        if variation.days:
            if current_day not in variation.days:
                matches = False

        # Check time range match
        if variation.time and matches:
            time_str = variation.time
            if "-" in time_str:
                start_str, end_str = time_str.split("-", 1)
                start_time = _parse_time(start_str)
                end_time = _parse_time(end_str)

                if not (start_time <= current_time <= end_time):
                    matches = False
            else:
                # Single time point - not supported for ranges
                matches = False

        if matches:
            multiplier = variation.multiplier
            break

    return base_rate * multiplier


def _parse_time(time_str: str) -> time:
    """Parse time string (HH:MM format) to time object.

    Args:
        time_str: Time string in HH:MM format

    Returns:
        time object
    """
    try:
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    except (ValueError, AttributeError):
        # Default to midnight if parsing fails
        return time(0, 0)


def calculate_rate_from_template_metadata(
    metadata: TemplateMetadata, timezone: str = "UTC"
) -> float:
    """Calculate current event rate from template metadata.

    Uses base_frequency (events per hour), time_patterns, and multipliers
    to determine the current rate in events per second.

    Args:
        metadata: Template metadata with frequency information
        timezone: Timezone string (e.g., 'America/New_York'). Defaults to UTC.

    Returns:
        Current rate in events per second
    """
    # If no base_frequency defined, default to 1 event per second
    if not metadata.base_frequency:
        return 1.0

    # If base_frequency is explicitly set to 0 or negative, return 0 (no events)
    if metadata.base_frequency <= 0:
        return 0.0

    # Convert base_frequency (events/hour) to base_rate (events/second)
    base_rate = metadata.base_frequency / 3600.0

    # If no time patterns defined, return base rate
    if not metadata.time_patterns:
        return base_rate

    # Get current time and day in specified timezone
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        # Invalid timezone, fall back to UTC
        tz = ZoneInfo("UTC")

    now = datetime.now(tz)
    current_day = now.isoweekday()  # 1=Monday, 7=Sunday
    current_time = now.time()

    # Determine multiplier based on time patterns
    # Priority: business_hours > night_hours > weekend
    # Business hours: Mon-Fri, 09:00-17:00
    if "business_hours" in metadata.time_patterns:
        if current_day in [1, 2, 3, 4, 5]:  # Mon-Fri
            if time(9, 0) <= current_time <= time(17, 0):
                multiplier = (
                    metadata.business_hours_multiplier
                    if metadata.business_hours_multiplier is not None
                    else 1.0
                )
                return base_rate * multiplier

    # Weekend: Sat-Sun (check before night_hours to avoid conflicts)
    if "weekend" in metadata.time_patterns:
        if current_day in [6, 7]:  # Sat-Sun
            multiplier = (
                metadata.weekend_multiplier if metadata.weekend_multiplier is not None else 1.0
            )
            return base_rate * multiplier

    # Night hours: Mon-Fri, outside business hours (17:00-09:00 next day)
    if "night_hours" in metadata.time_patterns:
        if current_day in [1, 2, 3, 4, 5]:  # Mon-Fri
            # Night hours are either after 17:00 or before 09:00
            if current_time >= time(17, 0) or current_time < time(9, 0):
                multiplier = (
                    metadata.night_hours_multiplier
                    if metadata.night_hours_multiplier is not None
                    else 1.0
                )
                return base_rate * multiplier

    # Default: no multiplier applied
    return base_rate
