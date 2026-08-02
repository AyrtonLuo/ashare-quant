"""
test_historical_point_in_time.py — Warehouse PIT Filtering Tests.
"""

from datetime import datetime
from src.data.warehouse.warehouse_loader import HistoricalDataWarehouse


def test_warehouse_pit_gating():
    wh = HistoricalDataWarehouse()
    as_of = datetime(2026, 4, 15, 15, 0)
    bars = wh.get_pit_market_bars("600519.SH", "2026-04-01", "2026-04-10", as_of)
    assert len(bars) == 1
    assert bars[0].available_at <= as_of
