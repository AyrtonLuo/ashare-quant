"""
test_snapshot_immutability.py — Audit test proving Snapshot A remains 100% immutable after new data/revisions arrive.
"""

import hashlib
import json
from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager


def test_snapshot_remains_immutable_after_subsequent_revisions():
    store = RevisionStore()

    # Step 1: Initial data available at T1
    rev_t1 = DataRevision(
        record_id="rec_01",
        symbol="600519.SH",
        field="close",
        effective_date="2022-05-01",
        value=1600.0,
        provider="tushare",
        available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 5),
        revision_id="rev_1",
        dataset_version="ds_v1"
    )
    store.add_revision(rev_t1)

    mgr = SnapshotManager(revision_store=store)
    
    # Create Snapshot A at T1 (2022-05-02)
    snap_a = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_A_20220502")

    # Step 2: Query Snapshot A and record result hash
    res1 = mgr.query_market_data("600519.SH", "2022-05-01", "2022-05-01", snapshot_id=snap_a.snapshot_id)
    hash_before = hashlib.sha256(json.dumps([c.value for c in res1]).encode()).hexdigest()

    # Step 3: Ingest newer provider data (Revision 2 added later at T2)
    rev_t2 = DataRevision(
        record_id="rec_02",
        symbol="600519.SH",
        field="close",
        effective_date="2022-05-01",
        value=1650.0, # Restated price
        provider="tushare",
        available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 6, 1, 15, 5), # Ingested in June!
        revision_id="rev_2",
        dataset_version="ds_v2"
    )
    store.add_revision(rev_t2)

    # Step 4: Query Snapshot A again
    res2 = mgr.query_market_data("600519.SH", "2022-05-01", "2022-05-01", snapshot_id=snap_a.snapshot_id)
    hash_after = hashlib.sha256(json.dumps([c.value for c in res2]).encode()).hexdigest()

    # Step 5: Assert 100% immutability
    assert hash_before == hash_after
    assert res1[0].value == res2[0].value == 1600.0
