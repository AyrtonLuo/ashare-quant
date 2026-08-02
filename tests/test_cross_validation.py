"""
test_cross_validation.py — Cross-Provider Validation Tests.
"""

from src.data.providers.tushare_provider import TuShareAdapter
from src.data.providers.akshare_provider import AkShareProviderAdapter
from src.data.validation.cross_validator import CrossProviderValidator, CrossValidationStatus


def test_cross_provider_market_data_match():
    tushare = TuShareAdapter()
    akshare = AkShareProviderAdapter()

    p_data = tushare.fetch_market_data("600519.SH", "2026-08-01")
    s_data = akshare.fetch_market_data("600519.SH", "2026-08-01")

    res = CrossProviderValidator.compare_market_close(p_data, s_data)
    assert res.status == CrossValidationStatus.MATCH
    assert res.rel_diff_pct == 0.0
