"""
trading_calendar.py — Canonical Trading Calendar for China A-Share Market.
"""

from typing import List, Set, Optional


class TradingCalendar:

    """Canonical China A-Share Trading Calendar Engine."""

    def __init__(self, trading_days: Optional[List[str]] = None):
        # Default representative A-Share trading calendar dates for testing
        self._trading_days: Set[str] = set(trading_days or [
            "2026-08-01", "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"
        ])

    def is_trading_day(self, date_str: str) -> bool:
        """Returns True if date_str (YYYY-MM-DD) is an official trading day."""
        return date_str in self._trading_days

    def get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """Returns sorted list of trading dates between start_date and end_date."""
        return sorted([d for d in self._trading_days if start_date <= d <= end_date])
