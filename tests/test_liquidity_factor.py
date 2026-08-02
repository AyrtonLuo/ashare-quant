"""
test_liquidity_factor.py — Unit Tests for Average Volume Factor.
"""

from datetime import datetime
from src.quant.factors.liquidity import AverageVolumeFactor
from src.quant.factors.base import FactorStatus


def test_liquidity_factor_calculation():
    factor = AverageVolumeFactor(window_days=5)
    vols = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
    now = datetime.now()

    res = factor.compute("600519.SH", vols, "2026-08-01", now)
    assert res.status == FactorStatus.VALID
    assert res.raw_value == 3000.0
