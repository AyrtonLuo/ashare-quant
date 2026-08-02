"""
test_backtest_no_lookahead.py — Point-in-time Gating Backtest Tests.
"""

from datetime import datetime
from src.quant.data.research_api import ResearchDataAPI


def test_backtest_queries_use_past_as_of_only():
    api = ResearchDataAPI()
    cutoff_t1 = datetime(2026, 4, 15, 15, 0)
    
    # Query at T1=2026-04-15
    bars = api.get_prices(["600519.SH"], "2026-08-01", "2026-08-01", as_of=cutoff_t1)
    # Available date in August 2026 is strictly blocked at April 2026 query
    assert len(bars) == 0
