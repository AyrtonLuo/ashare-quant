"""
test_data_contracts.py — Data Contract Schema & Integrity Tests.
"""

import pytest
from datetime import datetime
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.contracts.lineage import DataLineageContract


def test_market_data_contract_valid():
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
    assert contract.symbol == "600519.SH"
    assert contract.close_price == 1650.0


def test_market_data_contract_invalid_symbol():
    with pytest.raises(ValueError, match="Invalid symbol format"):
        MarketDataContract(
            symbol="600519",  # Missing .SH
            timestamp=datetime.now(),
            trading_date="2026-08-01",
            open_price=10.0,
            high_price=11.0,
            low_price=9.0,
            close_price=10.5,
            volume=100.0,
            amount=1000.0,
            adj_factor=1.0,
            unadjusted_close=10.5,
            trading_status="NORMAL",
            quality_status="VALID"
        )


def test_market_data_contract_invalid_price_bounds():
    with pytest.raises(ValueError, match="high .* < low"):
        MarketDataContract(
            symbol="000001.SZ",
            timestamp=datetime.now(),
            trading_date="2026-08-01",
            open_price=10.0,
            high_price=8.0,  # High < Low!
            low_price=9.0,
            close_price=9.5,
            volume=100.0,
            amount=1000.0,
            adj_factor=1.0,
            unadjusted_close=9.5,
            trading_status="NORMAL",
            quality_status="VALID"
        )


def test_corporate_action_contract():
    ca = CorporateActionContract(
        symbol="600519.SH",
        ex_date="2026-06-15",
        action_type="CASH_DIVIDEND",
        cash_amount_per_share=25.0,
        bonus_ratio=0.0,
        split_ratio=1.0,
        announcement_date="2026-05-20",
        available_at=datetime(2026, 5, 20, 15, 0),
        received_at=datetime(2026, 5, 20, 15, 0),
        quality_status="VALID"
    )
    assert ca.cash_amount_per_share == 25.0
