"""
test_research_run_reproducibility.py — Audit test proving ResearchRunManifest determinism across snapshot queries.
"""

from src.quant.reproducibility.manifest import ResearchRunManager
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from datetime import datetime


def test_research_run_manifest_reproducibility_with_snapshots():
    store = RevisionStore()
    rev1 = DataRevision(
        record_id="r1", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1600.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0), revision_id="rev_1", dataset_version="ds_v1"
    )
    store.add_revision(rev1)

    mgr = SnapshotManager(revision_store=store)
    snap = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_run_01")

    prices = {"600519.SH": [1600.0, 1620.0, 1610.0]}
    params = {"top_n": 1, "factor": "momentum"}

    # Run A
    manifest_a = ResearchRunManager.create_run_manifest(
        run_id="run_A", created_at="2022-05-02T10:00:00",
        dataset_id="ds_v1", dataset_payload=prices,
        strategy_id="strat_mom", strategy_version="1.0.0",
        parameters=params, cost_model_version="1.0.0",
        sharpe_ratio=1.85, total_return=0.12, max_drawdown=0.04,
        snapshot_id=snap.snapshot_id, dataset_version="ds_v1", as_of="2022-05-02T00:00:00"
    )

    # Run B (Same Snapshot & Parameters)
    manifest_b = ResearchRunManager.create_run_manifest(
        run_id="run_B", created_at="2022-05-02T10:00:00",
        dataset_id="ds_v1", dataset_payload=prices,
        strategy_id="strat_mom", strategy_version="1.0.0",
        parameters=params, cost_model_version="1.0.0",
        sharpe_ratio=1.85, total_return=0.12, max_drawdown=0.04,
        snapshot_id=snap.snapshot_id, dataset_version="ds_v1", as_of="2022-05-02T00:00:00"
    )

    # Ingest newer revision to store
    rev2 = DataRevision(
        record_id="r2", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1650.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 6, 1, 15, 0), revision_id="rev_2", dataset_version="ds_v2"
    )
    store.add_revision(rev2)

    # Run C (Re-run using old snapshot)
    manifest_c = ResearchRunManager.create_run_manifest(
        run_id="run_C", created_at="2022-06-02T10:00:00",
        dataset_id="ds_v1", dataset_payload=prices,
        strategy_id="strat_mom", strategy_version="1.0.0",
        parameters=params, cost_model_version="1.0.0",
        sharpe_ratio=1.85, total_return=0.12, max_drawdown=0.04,
        snapshot_id=snap.snapshot_id, dataset_version="ds_v1", as_of="2022-05-02T00:00:00"
    )

    assert manifest_a.dataset_hash == manifest_b.dataset_hash == manifest_c.dataset_hash
    assert manifest_a.result_hash == manifest_b.result_hash == manifest_c.result_hash
    assert manifest_a.snapshot_id == manifest_c.snapshot_id == "snap_run_01"
