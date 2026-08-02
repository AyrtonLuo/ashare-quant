"""
test_historical_pit_query.py — Tests verifying PIT filtering on Warehouse queries.
"""

from datetime import datetime
from src.data.warehouse.warehouse_loader import HistoricalDataWarehouse


def test_warehouse_pit_query_execution():
    wh = HistoricalDataWarehouse()
    cutoff_after = datetime(2026, 8, 1, 15, 0)
    bars = wh.get_pit_market_bars("600519.SH", "2026-08-01", "2026-08-01", cutoff_after)
    assert len(bars) == 1
    assert bars[0].available_at <= cutoff_after
