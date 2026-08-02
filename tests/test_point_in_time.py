"""
test_point_in_time.py — PIT Gate Tests verifying available_at vs query cutoff date.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification
from src.data.validation.pit_gate import PITGate


def test_pit_gate_filtering():
    announcement_time = datetime(2026, 4, 28, 18, 0)
    
    contract = TemporalDataContract(
        symbol="600519.SH",
        value=58.00,  # EPS
        temporal_class=TemporalClassification.POINT_IN_TIME,
        event_time=datetime(2026, 3, 31, 23, 59),
        effective_date="2026-03-31",
        available_at=announcement_time,
        received_at=announcement_time,
        as_of=announcement_time
    )

    cutoff_before = datetime(2026, 4, 1, 9, 30)
    cutoff_after = datetime(2026, 4, 29, 9, 30)

    assert PITGate.is_pit_valid(contract, cutoff_before) is False  # Blocked!
    assert PITGate.is_pit_valid(contract, cutoff_after) is True   # Allowed!
