"""
test_factor_missing_data.py — Tests verifying factor handling of missing history.
"""

from datetime import datetime
from src.quant.factors.momentum import PriceMomentumFactor
from src.quant.factors.base import FactorStatus


def test_factor_insufficient_history_status():
    factor = PriceMomentumFactor(window_days=20)
    prices = [100.0, 101.0, 102.0]  # Only 3 prices
    now = datetime.now()

    res = factor.compute("600519.SH", prices, "2026-08-01", now)
    assert res.status == FactorStatus.INSUFFICIENT_HISTORY
    assert res.raw_value is None  # Missing != 0 !
