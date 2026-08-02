"""
test_golden_backtest.py — Golden Backtest Reproducibility Tests.
"""

from src.quant.reproducibility.manifest import ResearchRunManager
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget


def test_golden_backtest_reproducibility():
    prices = {"600519.SH": [1600.0, 1620.0, 1610.0, 1650.0, 1660.0]}
    targets = [PortfolioTarget("2026-08-01", "strat_1", {"600519.SH": 1.0}, 1.0)]
    
    engine = BacktestEngine()
    res1 = engine.run_backtest("golden_ds", "strat_1", prices, targets)
    res2 = engine.run_backtest("golden_ds", "strat_1", prices, targets)

    # Identical runs must produce 100% identical outputs
    assert res1.total_return == res2.total_return
    assert res1.sharpe_ratio == res2.sharpe_ratio

    manifest = ResearchRunManager.create_run_manifest(
        "run_001", "2026-08-02", "golden_ds", prices, "strat_1", "1.0.0",
        {"top_n": 1}, "1.0.0", res1.sharpe_ratio, res1.total_return, res1.max_drawdown
    )

    assert manifest.reproducibility_status == "VERIFIED"
