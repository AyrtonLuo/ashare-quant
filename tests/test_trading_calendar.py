"""
test_trading_calendar.py — Unit Tests for Canonical TradingCalendar.
"""

from src.data.calendar.trading_calendar import TradingCalendar


def test_trading_calendar_queries():
    cal = TradingCalendar()
    assert cal.is_trading_day("2026-08-01") is True
    assert cal.is_trading_day("2026-08-02") is False  # Weekend / Non-trading day
    
    trading_days = cal.get_trading_days("2026-08-01", "2026-08-05")
    assert "2026-08-01" in trading_days
    assert "2026-08-02" not in trading_days
