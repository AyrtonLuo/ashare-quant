"""
test_momentum_strategy.py — Unit Tests for Simple Momentum Strategy.
"""

from src.quant.signals.engine import SignalRecommendation
from src.quant.strategies.simple_momentum import SimpleMomentumStrategy


def test_simple_momentum_strategy_target_selection():
    strat = SimpleMomentumStrategy()
    signals = [
        SignalRecommendation("600519.SH", "2026-08-01", "mom", 1.5, 0.75, "BUY_BIAS"),
        SignalRecommendation("000858.SZ", "2026-08-01", "mom", 1.0, 0.50, "BUY_BIAS"),
        SignalRecommendation("000001.SZ", "2026-08-01", "mom", -1.0, -0.50, "SELL_BIAS"),
    ]

    target_weights = strat.generate_target_portfolio(signals, top_n=2)
    assert "600519.SH" in target_weights
    assert "000858.SZ" in target_weights
    assert "000001.SZ" not in target_weights
    assert sum(target_weights.values()) <= 1.0
