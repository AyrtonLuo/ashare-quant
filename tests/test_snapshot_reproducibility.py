"""
test_snapshot_reproducibility.py — Tests verifying identical output for queries using the same snapshot_id.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.data.research_api import ResearchDataAPI


def test_snapshot_reproducibility_deterministic():
    store = RevisionStore()
    rev1 = DataRevision(
        record_id="rec_001",
        symbol="600519.SH",
        field="close",
        effective_date="2022-06-15",
        value=1650.0,
        provider="tushare_pro",
        available_at=datetime(2022, 6, 15, 15, 0, 0),
        received_at=datetime(2022, 6, 15, 15, 30, 0),
        revision_id="rev_1",
        dataset_version="ds_v1.0"
    )
    store.add_revision(rev1)
    
    mgr = SnapshotManager(revision_store=store)
    snap = mgr.create_snapshot(as_of=datetime(2022, 6, 15, 18, 0, 0), snapshot_id="snap_20220615")

    api = ResearchDataAPI(snapshot_manager=mgr, revision_store=store)
    
    # Repeated calls with same snapshot_id must return identical data
    res1 = api.get_prices(["600519.SH"], "2022-06-15", "2022-06-15", snapshot_id=snap.snapshot_id)
    res2 = api.get_prices(["600519.SH"], "2022-06-15", "2022-06-15", snapshot_id=snap.snapshot_id)

    assert len(res1) == 1
    assert len(res2) == 1
    assert res1[0].value == res2[0].value == 1650.0
    assert res1[0].available_at == res2[0].available_at
