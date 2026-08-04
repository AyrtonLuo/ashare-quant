"""
test_live_snapshot_temporal_isolation.py — Live PIT snapshot temporal isolation test.
"""

from datetime import datetime
import pytest
from src.data.revision.revision_store import RevisionStore
from src.data.revision.revision_model import DataRevision
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_snapshot_temporal_isolation_no_future_leaks():
    store = RevisionStore()
    rev_2021 = DataRevision(
        record_id="rec_1", symbol="600519.SH", field="close", effective_date="2021-01-04",
        value=1800.0, provider="tushare_pro_primary", available_at=datetime(2021, 1, 4, 15, 0),
        received_at=datetime(2021, 1, 4, 15, 5), revision_id="rev_2021", dataset_version="ds_live_v2.0"
    )
    rev_2023 = DataRevision(
        record_id="rec_2", symbol="600519.SH", field="close", effective_date="2023-01-04",
        value=1900.0, provider="tushare_pro_primary", available_at=datetime(2023, 1, 4, 15, 0),
        received_at=datetime(2023, 1, 4, 15, 5), revision_id="rev_2023", dataset_version="ds_live_v2.0"
    )
    store.add_revision(rev_2021)
    store.add_revision(rev_2023)

    snap_mgr = SnapshotManager(revision_store=store)
    snap = snap_mgr.create_snapshot(
        as_of=datetime(2022, 5, 2), snapshot_id="snap_2022", dataset_version="ds_live_v2.0"
    )

    bars = snap_mgr.query_market_data("600519.SH", "2021-01-01", "2023-12-31", snapshot_id="snap_2022")
    dates = [b.effective_date for b in bars]

    assert "2021-01-04" in dates
    assert "2023-01-04" not in dates  # 2023 record must NOT exist in 2022 snapshot!
