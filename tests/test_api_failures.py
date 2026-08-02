"""
test_api_failures.py — API Failure & Trapping Edge Case Tests.
"""

import pytest
from src.data.providers.base import ProviderError
from src.data.providers.tushare_provider import TuShareAdapter


def test_api_invalid_symbol_error_trapping():
    adapter = TuShareAdapter()
    with pytest.raises(ProviderError) as excinfo:
        adapter.fetch_market_data("INVALID_SYMBOL", "2026-08-01")
    
    assert "Invalid symbol format" in str(excinfo.value)
    assert excinfo.value.provider_id == "tushare_pro_primary"


def test_api_safe_failure_no_dummy_data():
    adapter = TuShareAdapter()
    # Ensure invalid fetch throws ProviderError instead of returning dummy 0 values
    with pytest.raises(ProviderError):
        adapter.fetch_market_data("BAD_TICKER", "2026-08-01")
