"""
test_portfolio_construction.py — Unit Tests for Portfolio Construction Engine.
"""

from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract
from src.quant.portfolio.construction import PortfolioConstructor


def test_portfolio_constructor_delisted_filter():
    reg = SecurityMasterRegistry()
    reg.register(SecurityMasterContract(
        symbol="600519.SH", exchange="SSE", display_name="贵州茅台",
        security_type="STOCK", list_date="2001-08-27", delist_date=None,
        status="ACTIVE", industry_sw_l1="食品饮料", industry_sw_l2="白酒"
    ))
    reg.register(SecurityMasterContract(
        symbol="600001.SH", exchange="SSE", display_name="退市科技",
        security_type="STOCK", list_date="2000-01-01", delist_date="2020-05-01",
        status="DELISTED", industry_sw_l1="电子", industry_sw_l2="半导体"
    ))

    raw_weights = {"600519.SH": 0.5, "600001.SH": 0.5}
    target = PortfolioConstructor.build_portfolio(raw_weights, "2026-08-01", "strat_v1", reg)

    # Delisted stock 600001.SH excluded from 2026 target weights
    assert "600519.SH" in target.weights
    assert "600001.SH" not in target.weights
    assert target.total_exposure <= 1.0
