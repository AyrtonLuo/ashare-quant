"""
test_current_value_leak.py — Audit test proving current values cannot leak into historical factor calculations.
"""

from datetime import datetime
from src.quant.factors.value import ValuationFactorAdapter
from src.quant.factors.base import FactorStatus
from src.data.contracts.fundamental_data import MetricProvenance


def test_valuation_factor_rejects_current_only_provenance():
    adapter = ValuationFactorAdapter("pe_ttm")
    
    # 1. Valid PIT provenance returns VALID
    val_pit = adapter.compute_from_fundamental(
        symbol="600519.SH", val=28.5, provenance=MetricProvenance.PROVIDER_REPORTED,
        effective_date="2022-03-31", as_of=datetime(2022, 5, 1)
    )
    assert val_pit.status == FactorStatus.VALID
    assert val_pit.raw_value == 28.5

    # 2. CURRENT_ONLY provenance returns NOT_APPLICABLE with raw_value=None
    val_curr = adapter.compute_from_fundamental(
        symbol="600519.SH", val=99.0, provenance=MetricProvenance.CURRENT_ONLY,
        effective_date="2022-03-31", as_of=datetime(2022, 5, 1)
    )
    assert val_curr.status == FactorStatus.NOT_APPLICABLE
    assert val_curr.raw_value is None

    # 3. NOT_PIT_VERIFIED provenance returns NOT_APPLICABLE with raw_value=None
    val_unverified = adapter.compute_from_fundamental(
        symbol="600519.SH", val=99.0, provenance=MetricProvenance.NOT_PIT_VERIFIED,
        effective_date="2022-03-31", as_of=datetime(2022, 5, 1)
    )
    assert val_unverified.status == FactorStatus.NOT_APPLICABLE
    assert val_unverified.raw_value is None
