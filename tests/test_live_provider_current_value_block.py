"""
test_live_provider_current_value_block.py — Current value leak blocking test.
"""

from datetime import datetime
import pytest
from src.quant.factors.value import ValuationFactorAdapter
from src.data.contracts.fundamental_data import MetricProvenance


def test_current_only_metric_blocked():
    adapter = ValuationFactorAdapter(metric_type="pe_ttm")
    res = adapter.compute_from_fundamental(
        symbol="600519.SH", val=35.0, provenance=MetricProvenance.CURRENT_ONLY,
        effective_date="2022-05-01", as_of=datetime(2022, 5, 1)
    )

    assert res.raw_value is None
    assert res.status.value == "NOT_APPLICABLE"
