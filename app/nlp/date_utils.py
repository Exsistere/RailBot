"""
Date utilities for deterministic weekday derivation.

travel_day should NOT be extracted by LLM. It is deterministically derived
from travel_date using Python's datetime module, which is the source of truth.

This module provides utilities for:
1. Deriving weekday names from ISO dates (deterministic)
2. Validating ISO date format (YYYY-MM-DD)
"""

from datetime import datetime


def derive_weekday(date_str: str) -> str:
    """
    Deterministically derive weekday name from ISO date string.
    
    Converts a date string (YYYY-MM-DD) to lowercase weekday name.
    This is the single source of truth for weekday derivation.
    
    Args:
        date_str: Date in ISO format (YYYY-MM-DD), e.g., "2026-06-15"
    
    Returns:
        Lowercase weekday name: "monday", "tuesday", ..., "sunday"
    
    Raises:
        ValueError: If date_str is not valid ISO format or date is invalid
    
    Examples:
        >>> derive_weekday("2026-06-15")
        "monday"
        >>> derive_weekday("2026-06-16")
        "tuesday"
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday_name = dt.strftime("%A").lower()
        return weekday_name
    except ValueError as e:
        raise ValueError(
            f"Invalid date format or date value: {date_str}. "
            f"Expected YYYY-MM-DD format. Error: {e}"
        )


def is_valid_iso_date(date_str: str) -> bool:
    """
    Validate ISO date format (YYYY-MM-DD).
    
    Args:
        date_str: Potential date string
    
    Returns:
        True if valid ISO date, False otherwise
    
    Examples:
        >>> is_valid_iso_date("2026-06-15")
        True
        >>> is_valid_iso_date("2026-6-15")
        False
        >>> is_valid_iso_date("invalid")
        False
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False
