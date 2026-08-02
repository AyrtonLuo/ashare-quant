"""
test_delayed_realtime.py — Tests verifying delayed data is never mislabelled as LIVE UI tag.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification, UIInterestTag


def test_delayed_data_ui_tag():
    event = datetime(2026, 8, 1, 10, 30, 0)
    rec = datetime(2026, 8, 1, 10, 31, 0)  # 60s delay
    contract = TemporalDataContract(
        symbol="600519.SH",
        value=1650.0,
        temporal_class=TemporalClassification.DELAYED_REALTIME,
        event_time=event,
        effective_date="2026-08-01",
        available_at=rec,
        received_at=rec,
        as_of=rec
    )
    assert contract.ui_tag == UIInterestTag.DELAYED  # Cannot be LIVE!
