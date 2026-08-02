"""
test_lookahead_prevention.py — Tests verifying report_date < announcement_date rules.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification
from src.data.validation.pit_gate import PITGate


def test_lookahead_prevention_during_backtest():
    """
    Ensures backtest at sim_date T=2026-04-15 cannot use Q1 2026 report
    if announced on 2026-04-28.
    """
    announcement_time = datetime(2026, 4, 28, 18, 0)
    
    q1_eps_contract = TemporalDataContract(
        symbol="600519.SH",
        value=15.0,
        temporal_class=TemporalClassification.POINT_IN_TIME,
        event_time=datetime(2026, 3, 31, 23, 59),
        effective_date="2026-03-31",
        available_at=announcement_time,
        received_at=announcement_time,
        as_of=announcement_time
    )

    backtest_sim_date = datetime(2026, 4, 15, 15, 0)
    
    # Must be BLOCKED from backtest at sim_date 2026-04-15
    assert PITGate.is_pit_valid(q1_eps_contract, backtest_sim_date) is False
