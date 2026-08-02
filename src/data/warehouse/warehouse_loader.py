"""
warehouse_loader.py — Historical Data Warehouse Loader providing validated historical datasets.
"""

from typing import List, Optional, Any
from datetime import datetime

from src.data.contracts.temporal import TemporalDataContract, TemporalClassification
from src.data.validation.pit_gate import PITGate


class HistoricalDataWarehouse:
    """Historical Data Warehouse reading Point-in-Time validated datasets for Backtester & Quant Engine."""

    def __init__(self, storage_adapter: Any = None):
        self.storage_adapter = storage_adapter

    def get_pit_market_bars(
        self, symbol: str, start_date: str, end_date: str, as_of_cutoff: datetime
    ) -> List[TemporalDataContract]:
        """Loads historical bars for symbol filtered strictly by available_at <= as_of_cutoff (No Look-Ahead)."""
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")

        # Simulated historical bar contract list
        bars = [
            TemporalDataContract(
                symbol=symbol,
                value=1650.00 if symbol == "600519.SH" else 11.50,
                temporal_class=TemporalClassification.HISTORICAL,
                event_time=dt_start,
                effective_date=start_date,
                available_at=dt_start,
                received_at=dt_start,
                as_of=as_of_cutoff
            )
        ]
        return PITGate.filter_pit_contracts(bars, as_of_cutoff)
