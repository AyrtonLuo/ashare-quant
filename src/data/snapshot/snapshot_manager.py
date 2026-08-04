"""
snapshot_manager.py — Snapshot Lifecycle & Mandatory PIT Query Gateway Engine with Strict Snapshot Isolation.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from src.data.snapshot.snapshot_model import DataSnapshot, SnapshotManifest, SnapshotManifestBuilder
from src.data.revision.revision_store import RevisionStore
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification
from src.data.contracts.fundamental_data import FundamentalDataContract, MetricProvenance


class SnapshotManager:
    """
    Manages logical Point-in-Time snapshots and enforces PIT query semantics across the system.
    Strictly isolates snapshots from future data ingestion and backfilled revisions.
    """

    def __init__(self, revision_store: Optional[RevisionStore] = None):
        self.revision_store = revision_store or RevisionStore()
        self._snapshots: Dict[str, DataSnapshot] = {}
        self._manifests: Dict[str, SnapshotManifest] = {}

    def create_snapshot(
        self,
        as_of: datetime,
        dataset_version: str = "ds_v1.0",
        provider_versions: Optional[Dict[str, str]] = None,
        snapshot_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> DataSnapshot:
        p_versions = provider_versions or {"tushare": "2.0", "akshare": "1.0"}
        sid = snapshot_id or f"snapshot_{as_of.strftime('%Y%m%d_%H%M%S')}"
        
        snapshot, manifest = SnapshotManifestBuilder.create_manifest(
            snapshot_id=sid,
            as_of=as_of,
            dataset_version=dataset_version,
            provider_versions=p_versions,
            parameters=parameters
        )

        self._snapshots[sid] = snapshot
        self._manifests[sid] = manifest
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[DataSnapshot]:
        return self._snapshots.get(snapshot_id)

    def get_manifest(self, snapshot_id: str) -> Optional[SnapshotManifest]:
        return self._manifests.get(snapshot_id)

    def query_snapshot(self, snapshot_id: str) -> DataSnapshot:
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            raise KeyError(f"Snapshot ID '{snapshot_id}' not found.")
        return snapshot

    def query_market_data(
        self,
        symbol: str,
        start: str,
        end: str,
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None
    ) -> List[TemporalDataContract]:
        """
        Queries historical market data bars filtered strictly by available_at <= as_of cutoff
        and received_at <= snapshot.created_at (Snapshot Isolation).
        """
        cutoff, created_at, dataset_ver = self._resolve_snapshot_metadata(as_of, snapshot_id)
        
        revs = self.revision_store.query_pit_range(
            symbol, "close", start, end, cutoff, received_before=created_at
        )
        contracts = []
        for r in revs:
            if r.available_at <= cutoff:
                contracts.append(
                    TemporalDataContract(
                        symbol=r.symbol,
                        value=r.value,
                        temporal_class=TemporalClassification.HISTORICAL,
                        event_time=r.available_at,
                        effective_date=r.effective_date,
                        available_at=r.available_at,
                        received_at=r.received_at,
                        as_of=cutoff,
                        provider_id=r.provider,
                        quality_status=r.quality_status
                    )
                )
        return contracts

    def query_fundamentals(
        self,
        symbol: str,
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None,
        effective_date: str = "2025-12-31"
    ) -> Optional[FundamentalDataContract]:
        """
        Queries fundamental data as of cutoff timestamp with snapshot isolation.
        """
        cutoff, created_at, _ = self._resolve_snapshot_metadata(as_of, snapshot_id)

        pe_rev = self.revision_store.query_pit(symbol, "pe_ttm", effective_date, cutoff, received_before=created_at)
        pb_rev = self.revision_store.query_pit(symbol, "pb", effective_date, cutoff, received_before=created_at)
        rev_rev = self.revision_store.query_pit(symbol, "revenue", effective_date, cutoff, received_before=created_at)
        net_rev = self.revision_store.query_pit(symbol, "net_income", effective_date, cutoff, received_before=created_at)
        div_rev = self.revision_store.query_pit(symbol, "dividend_yield_ttm", effective_date, cutoff, received_before=created_at)
        roe_rev = self.revision_store.query_pit(symbol, "roe", effective_date, cutoff, received_before=created_at)

        if not any([pe_rev, pb_rev, rev_rev, net_rev]):
            return None

        ann_date = pe_rev.available_at.strftime("%Y-%m-%d") if pe_rev else effective_date

        return FundamentalDataContract(
            symbol=symbol,
            trade_date=effective_date,
            report_date=effective_date,
            announcement_date=ann_date,
            currency="CNY",
            revenue=rev_rev.value if rev_rev else None,
            net_income=net_rev.value if net_rev else None,
            eps_annual=None,
            eps_ttm=None,
            book_value_per_share=None,
            operating_cash_flow=None,
            shares_outstanding=1.0e9,
            market_cap=1.0e10,
            pe_lyr=None,
            pe_ttm=pe_rev.value if pe_rev else None,
            pe_ttm_status="VALID" if pe_rev else "UNAVAILABLE",
            pb=pb_rev.value if pb_rev else None,
            pb_status="VALID" if pb_rev else "UNAVAILABLE",
            dividend_yield_ttm=div_rev.value if div_rev else None,
            dividend_yield_status="VALID" if div_rev else "UNAVAILABLE",
            roe=roe_rev.value if roe_rev else None,
            provenance=MetricProvenance.PROVIDER_REPORTED,
            quality_status="VALID"
        )

    def query_metric(
        self,
        symbol: str,
        metric: str,
        effective_date: str,
        as_of: Optional[datetime] = None,
        snapshot_id: Optional[str] = None
    ) -> Any:
        """
        Queries specific metric for symbol at effective_date with PIT enforcement as of cutoff.
        Returns metric value if available at cutoff; otherwise returns "UNAVAILABLE".
        """
        cutoff, created_at, _ = self._resolve_snapshot_metadata(as_of, snapshot_id)
        rev = self.revision_store.query_pit(symbol, metric, effective_date, cutoff, received_before=created_at)
        if rev is None or rev.available_at > cutoff:
            return "UNAVAILABLE"
        if rev.provenance in [MetricProvenance.CURRENT_ONLY, MetricProvenance.NOT_PIT_VERIFIED] or rev.quality_status == "CURRENT_ONLY":
            return "UNAVAILABLE"
        return rev.value

    def _resolve_snapshot_metadata(
        self, as_of: Optional[datetime], snapshot_id: Optional[str]
    ) -> Tuple[datetime, Optional[datetime], Optional[str]]:
        if snapshot_id:
            snapshot = self.query_snapshot(snapshot_id)
            return snapshot.as_of, snapshot.created_at, snapshot.dataset_version
        if as_of:
            return as_of, None, None
        raise ValueError("Either as_of datetime or snapshot_id must be provided to query under PIT semantics.")

    def _resolve_cutoff(self, as_of: Optional[datetime], snapshot_id: Optional[str]) -> datetime:
        cutoff, _, _ = self._resolve_snapshot_metadata(as_of, snapshot_id)
        return cutoff
