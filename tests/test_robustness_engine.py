"""
test_robustness_engine.py — Unit Tests for Parameter Sweeps & Out-of-Sample Split.
"""

from src.quant.research.robustness import RobustnessEngine


def test_robustness_time_series_split():
    days = [f"2026-08-{i:02d}" for i in range(1, 11)]
    train, val, test = RobustnessEngine.split_time_series(days, 0.6, 0.2)

    assert len(train) == 6
    assert len(val) == 2
    assert len(test) == 2
    # Ensure chronological order without overlap
    assert train[-1] < val[0] < test[0]
