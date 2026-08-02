"""
test_signal_engine.py — Unit Tests for Signal Engine recommendation emission.
"""

from src.quant.signals.engine import SignalEngine


def test_signal_engine_recommendations():
    scores = {"600519.SH": 1.5, "000001.SZ": -1.2, "000858.SZ": 0.1}
    signals = SignalEngine.generate_signals(scores, "mom_20d", "2026-08-01")

    assert len(signals) == 3
    s_maotai = next(s for s in signals if s.symbol == "600519.SH")
    assert s_maotai.bias_category == "BUY_BIAS"

    s_pingan = next(s for s in signals if s.symbol == "000001.SZ")
    assert s_pingan.bias_category == "SELL_BIAS"
