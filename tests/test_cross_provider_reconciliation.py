"""
test_cross_provider_reconciliation.py — Reconciliation tests for CrossProviderReconciler.
"""

from datetime import datetime
import pytest
from src.data.contracts.market_data import MarketDataContract
from src.data.validation.cross_provider import CrossProviderReconciler, ReconciliationStatus


def test_reconciler_match_classification():
    m1 = MarketDataContract(
        symbol="600519.SH", timestamp=datetime.now(), trading_date="2022-05-01",
        open_price=1650.0, high_price=1660.0, low_price=1640.0, close_price=1650.0,
        volume=50000.0, amount=82500000.0, adj_factor=1.0, unadjusted_close=1650.0,
        trading_status="NORMAL", quality_status="VALID"
    )
    m2 = MarketDataContract(
        symbol="600519.SH", timestamp=datetime.now(), trading_date="2022-05-01",
        open_price=1650.0, high_price=1660.0, low_price=1640.0, close_price=1650.5,
        volume=50000.0, amount=82525000.0, adj_factor=1.0, unadjusted_close=1650.5,
        trading_status="NORMAL", quality_status="VALID"
    )

    report = CrossProviderReconciler.reconcile_market_data(m1, m2)
    assert report.status in [ReconciliationStatus.MATCH, ReconciliationStatus.ACCEPTABLE_DIFFERENCE]


def test_reconciler_material_difference_classification():
    m1 = MarketDataContract(
        symbol="600519.SH", timestamp=datetime.now(), trading_date="2022-05-01",
        open_price=1650.0, high_price=1660.0, low_price=1640.0, close_price=1650.0,
        volume=50000.0, amount=82500000.0, adj_factor=1.0, unadjusted_close=1650.0,
        trading_status="NORMAL", quality_status="VALID"
    )
    m2 = MarketDataContract(
        symbol="600519.SH", timestamp=datetime.now(), trading_date="2022-05-01",
        open_price=1650.0, high_price=1660.0, low_price=1640.0, close_price=1900.0, # 15% diff!
        volume=50000.0, amount=95000000.0, adj_factor=1.0, unadjusted_close=1900.0,
        trading_status="NORMAL", quality_status="VALID"
    )

    report = CrossProviderReconciler.reconcile_market_data(m1, m2)
    assert report.status == ReconciliationStatus.MATERIAL_DIFFERENCE
