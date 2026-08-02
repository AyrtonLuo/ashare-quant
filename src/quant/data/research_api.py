"""
research_api.py — Research Data Access Layer wrapping HistoricalDataWarehouse with Point-in-Time gating.
"""

from datetime import datetime
from typing import List, Optional
from src.data.warehouse.warehouse_loader import HistoricalDataWarehouse
from src.data.contracts.temporal import TemporalDataContract


class ResearchDataAPI:
    """Research Data API providing Point-in-Time clean data queries for Factor Engine & Backtester."""

    def __init__(self, warehouse: Optional[HistoricalDataWarehouse] = None):
        self.warehouse = warehouse or HistoricalDataWarehouse()

    def get_prices(
        self, symbols: List[str], start_date: str, end_date: str, as_of: Optional[datetime] = None
    ) -> List[TemporalDataContract]:
        as_of_cutoff = as_of or datetime.now()
        contracts = []
        for symbol in symbols:
            bars = self.warehouse.get_pit_market_bars(symbol, start_date, end_date, as_of_cutoff)
            contracts.extend(bars)
        return contracts
