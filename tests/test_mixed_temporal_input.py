"""
test_mixed_temporal_input.py — Audit test proving derived metrics preserve strict input snapshot lineage.
"""

from datetime import datetime
from src.data.contracts.derived import DerivedDataContract
from src.data.contracts.temporal import TemporalClassification


def test_derived_metric_preserves_temporal_lineage():
    derived = DerivedDataContract(
        symbol="600519.SH",
        metric_name="momentum_composite",
        calculated_value=0.15,
        derived_at=datetime(2022, 5, 1, 15, 0),
        formula_version="1.0.0",
        input_data_ids=["rec_price_01", "rec_price_02"],
        input_as_of=datetime(2022, 5, 1, 15, 0),
        input_snapshot_id="snap_20220501_v1",
        calculation_timestamp=datetime(2022, 5, 1, 15, 0)
    )

    assert derived.input_snapshot_id == "snap_20220501_v1"
    assert derived.calculation_timestamp == datetime(2022, 5, 1, 15, 0)

    temporal = derived.to_temporal_contract()
    assert temporal.temporal_class == TemporalClassification.DERIVED
    assert temporal.as_of == datetime(2022, 5, 1, 15, 0)
    assert temporal.available_at <= temporal.as_of
