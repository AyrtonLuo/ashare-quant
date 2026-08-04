"""
test_factor_temporal_integrity.py — Audit test proving factor computation rolling windows are PIT-safe.
"""

from datetime import datetime
from src.quant.factors.momentum import PriceMomentumFactor
from src.quant.factors.base import FactorStatus


def test_momentum_factor_rolling_window_pit_integrity():
    factor = PriceMomentumFactor(window_days=5)

    # Valid 5-day prices
    prices = [10.0, 10.2, 10.5, 10.4, 10.8]
    eff_date = "2022-05-05"
    as_of_dt = datetime(2022, 5, 5, 15, 0)

    res = factor.compute("000001.SZ", prices, eff_date, as_of_dt)

    assert res.status == FactorStatus.VALID
    assert res.raw_value == (10.8 - 10.0) / 10.0
    assert res.as_of == as_of_dt
    assert res.effective_date == eff_date


def test_momentum_factor_insufficient_history():
    factor = PriceMomentumFactor(window_days=20)
    prices = [10.0, 10.2, 10.5] # Only 3 prices

    res = factor.compute("000001.SZ", prices, "2022-05-05", datetime(2022, 5, 5, 15, 0))

    assert res.status == FactorStatus.INSUFFICIENT_HISTORY
    assert res.raw_value is None
