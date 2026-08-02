"""
test_temporal_contract.py — Tests for TemporalDataContract and UI Interest Tags.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification, UIInterestTag


def test_temporal_contract_realtime():
    now = datetime.now()
    contract = TemporalDataContract(
        symbol="600519.SH",
        value=1650.0,
        temporal_class=TemporalClassification.REALTIME,
        event_time=now,
        effective_date="2026-08-01",
        available_at=now,
        received_at=now,
        as_of=now
    )
    assert contract.symbol == "600519.SH"
    assert contract.ui_tag == UIInterestTag.LIVE


def test_temporal_contract_historical():
    dt = datetime(2025, 1, 15, 15, 0)
    contract = TemporalDataContract(
        symbol="000001.SZ",
        value=11.50,
        temporal_class=TemporalClassification.HISTORICAL,
        event_time=dt,
        effective_date="2025-01-15",
        available_at=dt,
        received_at=dt,
        as_of=dt
    )
    assert contract.ui_tag == UIInterestTag.HISTORICAL
