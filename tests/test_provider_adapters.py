"""
test_provider_adapters.py — Unit Tests for Unified Provider Adapters (TuShare & AkShare).
"""

from src.data.providers.tushare_provider import TuShareAdapter
from src.data.providers.akshare_provider import AkShareProviderAdapter
from src.data.providers.base import ProviderError
import pytest


def test_tushare_adapter_fetch_market_data():
    adapter = TuShareAdapter()
    market_data = adapter.fetch_market_data("600519.SH", "2026-08-01")
    assert market_data is not None
    assert market_data.symbol == "600519.SH"
    assert market_data.close_price == 1650.0
    assert market_data.quality_status == "VALID"


def test_tushare_adapter_invalid_symbol():
    adapter = TuShareAdapter()
    with pytest.raises(ProviderError, match="Invalid symbol format"):
        adapter.fetch_market_data("600519", "2026-08-01")


def test_akshare_adapter_fetch_fundamental_data():
    adapter = AkShareProviderAdapter()
    fund = adapter.fetch_fundamental_data("600519.SH", "2026-08-01")
    assert fund is not None
    assert fund.pe_lyr == 28.4483
    assert fund.pe_ttm_status == "VALID"
