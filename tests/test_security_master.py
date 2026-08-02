"""
test_security_master.py — Unit Tests for SecurityMaster & Survivorship Bias Prevention.
"""

from src.data.domain.security_master import SecurityMasterContract, SecurityMasterRegistry


def test_security_master_tradability_and_delisting():
    registry = SecurityMasterRegistry()
    
    # Active Stock
    registry.register(SecurityMasterContract(
        symbol="600519.SH", exchange="SSE", display_name="贵州茅台",
        security_type="STOCK", list_date="2001-08-27", delist_date=None,
        status="ACTIVE", industry_sw_l1="食品饮料", industry_sw_l2="白酒"
    ))
    
    # Delisted Stock
    registry.register(SecurityMasterContract(
        symbol="600001.SH", exchange="SSE", display_name="退市科技",
        security_type="STOCK", list_date="2000-01-01", delist_date="2020-05-01",
        status="DELISTED", industry_sw_l1="电子", industry_sw_l2="半导体"
    ))

    # Active stock is tradable today
    assert registry.is_tradable_on("600519.SH", "2026-08-01") is True
    
    # Delisted stock was tradable in 2015, but NOT tradable in 2026!
    assert registry.is_tradable_on("600001.SH", "2015-06-01") is True
    assert registry.is_tradable_on("600001.SH", "2026-08-01") is False  # Prevents Survivorship Bias!
