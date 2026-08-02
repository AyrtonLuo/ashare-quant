"""
test_performance_metrics.py — Unit Tests for Performance Analytics.
"""

from src.quant.performance.analytics import PerformanceAnalytics


def test_performance_sharpe_and_drawdown():
    returns = [0.01, 0.02, -0.005, 0.015, -0.01]
    equity = [100.0, 102.0, 105.0, 98.0, 103.0]

    sharpe = PerformanceAnalytics.calculate_sharpe(returns, risk_free_rate=0.02)
    max_dd = PerformanceAnalytics.calculate_max_drawdown(equity)

    assert max_dd == (105.0 - 98.0) / 105.0  # 7 / 105 = 0.06666...
    assert sharpe != 0.0
