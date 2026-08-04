"""
test_snapshot_query.py — Tests verifying standard query semantics: query_market_data, query_fundamentals, query_metric, query_snapshot.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_standard_snapshot_query_semantics():
    store = RevisionStore()

    # Add market price revision
    p_rev = DataRevision(
        record_id="p_01",
        symbol="600519.SH",
        field="close",
        effective_date="2022-06-15",
        value=1650.0,
        provider="tushare",
        available_at=datetime(2022, 6, 15, 15, 0),
        received_at=datetime(2022, 6, 15, 15, 0),
        revision_id="r_p1",
        dataset_version="ds_v1"
    )
    store.add_revision(p_rev)

    # Add fundamental PE revision
    f_rev = DataRevision(
        record_id="f_01",
        symbol="600519.SH",
        field="pe_ttm",
        effective_date="2022-03-31",
        value=28.5,
        provider="tushare",
        available_at=datetime(2022, 4, 28, 9, 0),
        received_at=datetime(2022, 4, 28, 9, 0),
        revision_id="r_f1",
        dataset_version="ds_v1"
    )
    store.add_revision(f_rev)

    mgr = SnapshotManager(revision_store=store)
    snap = mgr.create_snapshot(as_of=datetime(2022, 6, 20), snapshot_id="snap_test_001")

    # 1. query_snapshot
    s_fetched = mgr.query_snapshot("snap_test_001")
    assert s_fetched.snapshot_id == "snap_test_001"

    # 2. query_market_data
    bars = mgr.query_market_data("600519.SH", "2022-06-15", "2022-06-15", snapshot_id="snap_test_001")
    assert len(bars) == 1
    assert bars[0].value == 1650.0

    # 3. query_fundamentals
    fund = mgr.query_fundamentals("600519.SH", snapshot_id="snap_test_001", effective_date="2022-03-31")
    assert fund is not None
    assert fund.pe_ttm == 28.5

    # 4. query_metric
    pe_val = mgr.query_metric("600519.SH", "pe_ttm", "2022-03-31", snapshot_id="snap_test_001")
    assert pe_val == 28.5
