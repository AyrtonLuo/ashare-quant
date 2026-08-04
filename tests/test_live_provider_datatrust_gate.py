"""
test_live_provider_datatrust_gate.py — DataTrustGate verification test.
"""

from datetime import datetime
import pytest
from src.data.validation.gate import DataTrustGate
from src.data.contracts.market_data import MarketDataContract


def test_datatrust_gate_live_validation():
    contract = MarketDataContract(
        symbol="600519.SH", timestamp=datetime.now(), trading_date="2022-05-01",
        open_price=1650.0, high_price=1660.0, low_price=1640.0, close_price=1650.0,
        volume=50000.0, amount=82500000.0, adj_factor=1.0, unadjusted_close=1650.0,
        trading_status="NORMAL", quality_status="VALID"
    )
    is_valid, errors = DataTrustGate.validate_market_data(contract)
    assert is_valid is True
    assert len(errors) == 0
