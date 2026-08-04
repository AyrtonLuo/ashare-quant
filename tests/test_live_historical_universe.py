"""
test_live_historical_universe.py — Live historical universe behavior test.
"""

import pytest
from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract


def test_live_historical_universe_delisting_behavior():
    registry = SecurityMasterRegistry()
    sec = SecurityMasterContract(
        symbol="000003.SZ", exchange="SZSE", display_name="PT水仙", security_type="STOCK",
        list_date="2000-01-01", delist_date="2022-06-30", status="DELISTED",
        industry_sw_l1="A_SHARE", industry_sw_l2="STOCK"
    )
    registry.register(sec)

    assert "000003.SZ" in registry.get_historical_universe("2021-01-01")
    assert "000003.SZ" not in registry.get_historical_universe("2023-01-01")
