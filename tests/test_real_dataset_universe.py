"""
test_real_dataset_universe.py — Real historical universe survivorship bias tests.
"""

import pytest
from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract


def test_real_dataset_delisted_symbol_retained_in_past_universe():
    registry = SecurityMasterRegistry()
    sec = SecurityMasterContract(
        symbol="000003.SZ",
        exchange="SZSE",
        display_name="PT水仙",
        security_type="STOCK",
        list_date="2000-01-01",
        delist_date="2022-06-30",
        status="DELISTED",
        industry_sw_l1="A_SHARE",
        industry_sw_l2="STOCK"
    )
    registry.register(sec)

    past_universe = registry.get_historical_universe(as_of_date="2021-06-01")
    assert "000003.SZ" in past_universe

    future_universe = registry.get_historical_universe(as_of_date="2023-01-01")
    assert "000003.SZ" not in future_universe
