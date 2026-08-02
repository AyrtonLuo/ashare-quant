"""
test_strategy_comparison.py — Unit Tests for Strategy & Benchmark Comparison Engine.
"""

from src.quant.backtest.engine import BacktestResult
from src.quant.performance.comparison import StrategyComparator


def test_strategy_comparison_analytics():
    res_a = BacktestResult("ds1", "Strat_A", [100, 105], [0.05], 0.05, 0.12, 0.10, 1.2, 0.02, 0.8, 0.1, 1)
    b_returns = [0.02]

    comp = StrategyComparator.compare_against_benchmark(res_a, b_returns)
    assert comp.active_return > 0
    assert comp.information_ratio != 0.0
