"""
test_historical_survivorship_bias.py — Delisted Security Historical Retention Tests.
"""

from src.data.domain.security_master import SecurityMasterContract, SecurityMasterRegistry


def test_delisted_stock_retained_in_past_universe():
    registry = SecurityMasterRegistry()
    registry.register(SecurityMasterContract(
        symbol="600001.SH", exchange="SSE", display_name="退市科技",
        security_type="STOCK", list_date="2000-01-01", delist_date="2020-05-01",
        status="DELISTED", industry_sw_l1="电子", industry_sw_l2="半导体"
    ))

    # Retained in 2018 universe (No Survivorship Bias!)
    assert registry.is_tradable_on("600001.SH", "2018-06-01") is True
    # Excluded from 2026 universe
    assert registry.is_tradable_on("600001.SH", "2026-08-01") is False
