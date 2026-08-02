"""
test_backtest_engine.py — Unit Tests for Backtest Engine.
"""

from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget


def test_backtest_engine_simulation():
    engine = BacktestEngine()
    prices = {
        "600519.SH": [1600.0, 1620.0, 1610.0, 1650.0, 1660.0],
        "000001.SZ": [11.0, 11.2, 11.1, 11.3, 11.5]
    }
    targets = [
        PortfolioTarget("2026-08-01", "strat_1", {"600519.SH": 0.5, "000001.SZ": 0.5}, 1.0)
    ]

    res = engine.run_backtest("golden_ashare_daily_v1", "strat_1", prices, targets)
    assert res.total_return > 0
    assert len(res.equity_curve) == 5
    assert res.sharpe_ratio != 0.0
