"""
test_derived_data_lineage.py — Tests for DerivedDataContract lineage & inputs trace.
"""

from datetime import datetime
from src.data.contracts.derived import DerivedDataContract
from src.data.contracts.temporal import TemporalClassification


def test_derived_data_contract_lineage_trace():
    now = datetime.now()
    derived = DerivedDataContract(
        symbol="600519.SH",
        metric_name="realtime_pe_ttm",
        calculated_value=28.4483,
        derived_at=now,
        formula_version="1.0.0",
        input_data_ids=["market_quote_600519_20260801", "eps_ttm_600519_2026Q1"],
        input_as_of=now,
        quality_status="VALID"
    )
    
    assert derived.symbol == "600519.SH"
    assert len(derived.input_data_ids) == 2
    
    temp_contract = derived.to_temporal_contract()
    assert temp_contract.temporal_class == TemporalClassification.DERIVED
