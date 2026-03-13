"""Date/time utilities."""

from datetime import date, datetime
from typing import Any


def parse_date(date_str: str) -> date:
    """Parse date string in various formats."""
    formats = ["%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse date: {date_str}")


def format_date(dt: date | datetime, fmt: str = "%Y-%m-%d") -> str:
    """Format date to string."""
    return dt.strftime(fmt)


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string in various formats."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse datetime: {dt_str}")
