"""
test_data_validation.py — DataTrustGate Validation Tests.
"""

from datetime import datetime
from src.data.contracts.market_data import MarketDataContract
from src.data.validation.gate import DataTrustGate


def test_data_trust_gate_market_data_pass():
    contract = MarketDataContract(
        symbol="600519.SH",
        timestamp=datetime.now(),
        trading_date="2026-08-01",
        open_price=1640.0,
        high_price=1660.0,
        low_price=1630.0,
        close_price=1650.0,
        volume=50000.0,
        amount=82500000.0,
        adj_factor=1.0,
        unadjusted_close=1650.0,
        trading_status="NORMAL",
        quality_status="VALID"
    )
    is_valid, errors = DataTrustGate.validate_market_data(contract)
    assert is_valid is True
    assert len(errors) == 0


def test_data_trust_gate_market_data_reject_non_valid():
    contract = MarketDataContract(
        symbol="600519.SH",
        timestamp=datetime.now(),
        trading_date="2026-08-01",
        open_price=1640.0,
        high_price=1660.0,
        low_price=1630.0,
        close_price=1650.0,
        volume=50000.0,
        amount=82500000.0,
        adj_factor=1.0,
        unadjusted_close=1650.0,
        trading_status="NORMAL",
        quality_status="SUSPECT"  # Not VALID!
    )
    is_valid, errors = DataTrustGate.validate_market_data(contract)
    assert is_valid is False
    assert "Quality status is not VALID: SUSPECT" in errors[0]
