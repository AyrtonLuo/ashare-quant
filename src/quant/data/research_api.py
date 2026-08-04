"""
research_api.py — Research Data Access Layer wrapping SnapshotManager & RevisionStore with Point-in-Time gating.
"""

from datetime import datetime
from typing import List, Optional, Any
from src.data.warehouse.warehouse_loader import HistoricalDataWarehouse
from src.data.contracts.temporal import TemporalDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.revision.revision_store import RevisionStore


class ResearchDataAPI:
    """
    Research Data API providing Point-in-Time clean data queries for Factor Engine & Backtester.
    All queries pass through the mandatory Snapshot & PIT Layer.
    Strictly forbids un-gated query calls without an explicit as_of or snapshot_id.
    """

    def __init__(
        self,
        warehouse: Optional[HistoricalDataWarehouse] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        revision_store: Optional[RevisionStore] = None
    ):
        self.warehouse = warehouse or HistoricalDataWarehouse()
        self.revision_store = revision_store or RevisionStore()
        self.snapshot_manager = snapshot_manager or SnapshotManager(revision_store=self.revision_store)

    def get_prices(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None
    ) -> List[TemporalDataContract]:
        if not (as_of or snapshot_id):
            raise ValueError("ResearchDataAPI query requires an explicit as_of datetime or snapshot_id.")

        as_of_cutoff = self.snapshot_manager._resolve_cutoff(as_of, snapshot_id)
        
        contracts = []
        for symbol in symbols:
            pit_rev_contracts = self.snapshot_manager.query_market_data(
                symbol=symbol, start=start_date, end=end_date, as_of=as_of_cutoff, snapshot_id=snapshot_id
            )
            if pit_rev_contracts:
                contracts.extend(pit_rev_contracts)
            else:
                bars = self.warehouse.get_pit_market_bars(symbol, start_date, end_date, as_of_cutoff)
                contracts.extend(bars)

        return [c for c in contracts if c.available_at <= as_of_cutoff]

    def get_fundamentals(
        self,
        symbol: str,
        effective_date: str = "2025-12-31",
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None
    ) -> Optional[FundamentalDataContract]:
        if not (as_of or snapshot_id):
            raise ValueError("ResearchDataAPI query requires an explicit as_of datetime or snapshot_id.")
        return self.snapshot_manager.query_fundamentals(
            symbol=symbol, effective_date=effective_date, as_of=as_of, snapshot_id=snapshot_id
        )

    def get_metric(
        self,
        symbol: str,
        metric: str,
        effective_date: str,
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None
    ) -> Any:
        if not (as_of or snapshot_id):
            raise ValueError("ResearchDataAPI query requires an explicit as_of datetime or snapshot_id.")
        return self.snapshot_manager.query_metric(
            symbol=symbol, metric=metric, effective_date=effective_date, as_of=as_of, snapshot_id=snapshot_id
        )

    def query_snapshot(self, snapshot_id: str):
        return self.snapshot_manager.query_snapshot(snapshot_id)
