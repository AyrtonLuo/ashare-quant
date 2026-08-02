"""
test_historical_temporal_semantics.py — Tests verifying Historical Classification.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification, UIInterestTag


def test_historical_bar_classification():
    dt = datetime(2020, 1, 15, 15, 0)
    contract = TemporalDataContract(
        symbol="600519.SH",
        value=1100.0,
        temporal_class=TemporalClassification.HISTORICAL,
        event_time=dt,
        effective_date="2020-01-15",
        available_at=dt,
        received_at=datetime.now(),
        as_of=dt
    )
    assert contract.temporal_class == TemporalClassification.HISTORICAL
    assert contract.ui_tag == UIInterestTag.HISTORICAL
