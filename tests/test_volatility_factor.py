"""
test_volatility_factor.py — Unit Tests for Realized Volatility Factor.
"""

from datetime import datetime
from src.quant.factors.volatility import RealizedVolatilityFactor
from src.quant.factors.base import FactorStatus


def test_volatility_factor_calculation():
    factor = RealizedVolatilityFactor(window_days=5)
    prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0]
    now = datetime.now()

    res = factor.compute("600519.SH", prices, "2026-08-01", now)
    assert res.status == FactorStatus.VALID
    assert res.raw_value > 0.0
