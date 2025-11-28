"""Frequency calculation logic for generators."""

import time
from datetime import datetime
from typing import List, Optional

from logforge.core.config import FrequencyConfig, FrequencyVariation


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
            if '-' in time_str:
                start_str, end_str = time_str.split('-', 1)
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
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    except (ValueError, AttributeError):
        # Default to midnight if parsing fails
        return time(0, 0)

