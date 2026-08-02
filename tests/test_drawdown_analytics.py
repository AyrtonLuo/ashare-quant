"""
test_drawdown_analytics.py — Unit Tests for Drawdown Analytics.
"""

from src.quant.performance.drawdown import DrawdownAnalytics


def test_drawdown_analytics_recovery_duration():
    equity = [100.0, 105.0, 95.0, 100.0, 106.0]
    dates = ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]

    res = DrawdownAnalytics.analyze_drawdown(equity, dates)
    assert res.max_drawdown_pct == round((105.0 - 95.0) / 105.0, 4)
    assert res.start_date == "2026-08-02"
    assert res.bottom_date == "2026-08-03"
    assert res.recovery_date == "2026-08-05"
    assert res.recovery_days == 3
