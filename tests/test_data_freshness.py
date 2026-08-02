"""
test_data_freshness.py — Data Freshness & Market Session Tests.
"""

from datetime import datetime
from src.data.calendar.market_session import MarketSessionEngine, MarketSessionState
from src.data.freshness.freshness_model import FreshnessModel
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification


def test_market_session_open():
    dt_open = datetime(2026, 8, 3, 10, 0)  # Trading day morning session
    session = MarketSessionEngine.get_market_session(dt_open, is_trading_day=True)
    assert session == MarketSessionState.OPEN


def test_market_session_close():
    dt_close = datetime(2026, 8, 3, 16, 0)  # After 15:00 market close
    session = MarketSessionEngine.get_market_session(dt_close, is_trading_day=True)
    assert session == MarketSessionState.CLOSE


def test_data_freshness_age():
    event_time = datetime(2026, 8, 1, 10, 0, 0)
    now = datetime(2026, 8, 1, 10, 0, 15)
    contract = TemporalDataContract(
        symbol="600519.SH",
        value=1650.0,
        temporal_class=TemporalClassification.REALTIME,
        event_time=event_time,
        effective_date="2026-08-01",
        available_at=event_time,
        received_at=event_time,
        as_of=event_time
    )
    age = FreshnessModel.get_freshness_age_seconds(contract, now)
    assert age == 15.0
