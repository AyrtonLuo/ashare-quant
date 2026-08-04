"""
test_backtest_snapshot_integrity.py — Backtest Snapshot Integrity Tests.
"""

from datetime import datetime
from src.data.revision.revision_model import DataRevision
from src.data.revision.revision_store import RevisionStore
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget


def test_backtest_snapshot_integrity_unaffected_by_future_updates():
    """
    REQUIRED BACKTEST INTEGRITY TEST (CEO Directive Section 18):
    Same Strategy run on:
    Snapshot A (as_of = T1)
    Snapshot B (as_of = T2 > T1)

    Snapshot A's historical results must remain 100% unaffected by future revisions in Snapshot B.
    """
    store = RevisionStore()

    # T1 revision
    r_t1 = DataRevision(
        record_id="p1",
        symbol="600519.SH",
        field="close",
        effective_date="2022-05-01",
        value=1600.0,
        provider="tushare",
        available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0),
        revision_id="r1",
        dataset_version="ds_v1"
    )
    store.add_revision(r_t1)

    mgr = SnapshotManager(revision_store=store)
    snap_a = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_A_20220502")

    engine = BacktestEngine()
    prices_a = {"600519.SH": [1600.0, 1620.0, 1610.0]}
    targets = [PortfolioTarget("2022-05-01", "strat_1", {"600519.SH": 1.0}, 1.0)]

    res_a1 = engine.run_backtest("ds_v1", "strat_1", prices_a, targets, data_snapshot=snap_a)

    # Later T2 revision added (restatement in June)
    r_t2 = DataRevision(
        record_id="p1_revised",
        symbol="600519.SH",
        field="close",
        effective_date="2022-05-01",
        value=1650.0, # Restated price
        provider="tushare",
        available_at=datetime(2022, 6, 1, 15, 0),
        received_at=datetime(2022, 6, 1, 15, 0),
        revision_id="r2",
        dataset_version="ds_v2"
    )
    store.add_revision(r_t2)

    snap_b = mgr.create_snapshot(as_of=datetime(2022, 6, 2), snapshot_id="snap_B_20220602")

    # Re-running on Snapshot A MUST return exact same results as before
    res_a2 = engine.run_backtest("ds_v1", "strat_1", prices_a, targets, data_snapshot=snap_a)
    assert res_a1.total_return == res_a2.total_return
    assert res_a1.sharpe_ratio == res_a2.sharpe_ratio
    assert res_a1.snapshot_id == res_a2.snapshot_id == "snap_A_20220502"
