"""
test_historical_data_quality.py — Tests for Historical Data Quality Rules.
"""

from datetime import datetime
from src.data.contracts.market_data import MarketDataContract
from src.data.validation.gate import DataTrustGate


def test_historical_bar_high_low_consistency():
    bar = MarketDataContract(
        symbol="600519.SH",
        timestamp=datetime(2020, 5, 10, 15, 0),
        trading_date="2020-05-10",
        open_price=1300.0,
        high_price=1320.0,
        low_price=1290.0,
        close_price=1315.0,
        volume=20000.0,
        amount=26200000.0,
        adj_factor=1.0,
        unadjusted_close=1315.0,
        trading_status="NORMAL",
        quality_status="VALID"
    )
    is_valid, errors = DataTrustGate.validate_market_data(bar)
    assert is_valid is True
