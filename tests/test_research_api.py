"""
test_research_api.py — Unit Tests for Research Data Access Layer with as_of gating.
"""

from datetime import datetime
from src.quant.data.research_api import ResearchDataAPI


def test_research_api_as_of_gating():
    api = ResearchDataAPI()
    cutoff = datetime(2026, 8, 1, 15, 0)
    prices = api.get_prices(["600519.SH"], "2026-08-01", "2026-08-01", as_of=cutoff)
    assert len(prices) == 1
    assert prices[0].available_at <= cutoff
