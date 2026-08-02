"""
test_historical_cross_provider.py — Historical Cross Provider Verification Tests.
"""

from src.data.validation.cross_validator import CrossProviderValidator, CrossValidationStatus
from src.data.contracts.market_data import MarketDataContract
from datetime import datetime


def test_historical_close_cross_provider_check():
    now = datetime.now()
    p_bar = MarketDataContract(
        symbol="600519.SH", timestamp=now, trading_date="2020-01-15",
        open_price=1100.0, high_price=1115.0, low_price=1095.0, close_price=1110.0,
        volume=15000.0, amount=16650000.0, adj_factor=1.0, unadjusted_close=1110.0,
        trading_status="NORMAL", quality_status="VALID"
    )
    s_bar = MarketDataContract(
        symbol="600519.SH", timestamp=now, trading_date="2020-01-15",
        open_price=1100.0, high_price=1115.0, low_price=1095.0, close_price=1110.0,
        volume=15000.0, amount=16650000.0, adj_factor=1.0, unadjusted_close=1110.0,
        trading_status="NORMAL", quality_status="VALID"
    )
    res = CrossProviderValidator.compare_market_close(p_bar, s_bar)
    assert res.status == CrossValidationStatus.MATCH
