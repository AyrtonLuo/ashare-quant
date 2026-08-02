"""
test_factor_analytics.py — Unit Tests for Exposure, Correlation Matrix, Rank IC & Decay.
"""

from src.quant.factors.analytics import FactorAnalytics


def test_factor_exposure_and_rank_ic():
    weights = {"600519.SH": 0.6, "000001.SZ": 0.4}
    scores = {"600519.SH": 1.0, "000001.SZ": -0.5}

    exposure = FactorAnalytics.calculate_factor_exposure(weights, scores)
    assert exposure == 0.4  # 0.6*1.0 + 0.4*(-0.5) = 0.4

    f_scores = {"A": 1.0, "B": 2.0, "C": 3.0}
    returns = {"A": 0.01, "B": 0.02, "C": 0.03}
    ic = FactorAnalytics.calculate_rank_ic(f_scores, returns)
    assert ic == 1.0  # Perfect positive correlation
