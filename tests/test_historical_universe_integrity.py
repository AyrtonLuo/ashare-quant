"""
test_historical_universe_integrity.py — Audit test proving historical universe construction is PIT-aware and survivorship-bias-free.
"""

from src.data.domain.security_master import SecurityMasterContract, SecurityMasterRegistry


def test_historical_universe_and_pit_suspension():
    registry = SecurityMasterRegistry()

    # Stock 1: Listed 2010, Delisted 2020
    registry.register(SecurityMasterContract(
        symbol="600001.SH", exchange="SSE", display_name="退市科技",
        security_type="STOCK", list_date="2010-01-01", delist_date="2020-05-01",
        status="DELISTED", industry_sw_l1="电子", industry_sw_l2="半导体"
    ))

    # Stock 2: Listed 2019, Active
    registry.register(SecurityMasterContract(
        symbol="600519.SH", exchange="SSE", display_name="贵州茅台",
        security_type="STOCK", list_date="2019-01-01", delist_date=None,
        status="ACTIVE", industry_sw_l1="食品饮料", industry_sw_l2="白酒"
    ))

    # Register suspension for茅台 on 2022-06-15 only
    registry.register_suspension("600519.SH", "2022-06-15")

    # 1. Historical universe in 2015 includes Stock 1, excludes Stock 2 (not listed yet)
    u_2015 = registry.get_historical_universe("2015-06-01")
    assert "600001.SH" in u_2015
    assert "600519.SH" not in u_2015

    # 2. Historical universe in 2019 includes both Stock 1 & Stock 2
    u_2019 = registry.get_historical_universe("2019-06-01")
    assert "600001.SH" in u_2019
    assert "600519.SH" in u_2019

    # 3. Historical universe in 2022 excludes Stock 1 (delisted in 2020)
    u_2022 = registry.get_historical_universe("2022-06-01")
    assert "600001.SH" not in u_2022
    assert "600519.SH" in u_2022

    # 4. PIT Tradable checks
    assert registry.is_tradable_on("600519.SH", "2022-06-14") is True
    assert registry.is_tradable_on("600519.SH", "2022-06-15") is False  # Suspended on this date!
    assert registry.is_tradable_on("600519.SH", "2022-06-16") is True
