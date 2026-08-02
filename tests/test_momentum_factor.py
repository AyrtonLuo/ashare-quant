"""
test_momentum_factor.py — Unit Tests for Price Momentum Factor.
"""

from datetime import datetime
from src.quant.factors.momentum import PriceMomentumFactor
from src.quant.factors.base import FactorStatus


def test_momentum_factor_calculation():
    factor = PriceMomentumFactor(window_days=5)
    prices = [100.0, 102.0, 104.0, 103.0, 105.0]
    now = datetime.now()

    res = factor.compute("600519.SH", prices, "2026-08-01", now)
    assert res.status == FactorStatus.VALID
    assert res.raw_value == 0.05  # (105 - 100) / 100 = 0.05
