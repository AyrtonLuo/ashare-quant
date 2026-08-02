"""
test_portfolio_v2.py — Unit Tests for Portfolio Construction V2 & Position Limits.
"""

from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract
from src.quant.portfolio.construction_v2 import PortfolioConstructorV2


def test_portfolio_v2_max_position_limit():
    reg = SecurityMasterRegistry()
    reg.register(SecurityMasterContract("600519.SH", "SSE", "茅台", "STOCK", "2001-08-27", None, "ACTIVE", "食品", "白酒"))
    
    scores = {"600519.SH": 1.0}
    prev_w = {}
    target = PortfolioConstructorV2.build_portfolio_v2(
        scores, prev_w, "2026-08-01", "strat_v2", reg, max_position_limit=0.15
    )

    assert target.weights["600519.SH"] <= 0.15
