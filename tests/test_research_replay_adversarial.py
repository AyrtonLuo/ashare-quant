"""
test_research_replay_adversarial.py — Adversarial tests for research run replay, identity changes, and dataset locks.
"""

import pytest
import tempfile
from datetime import datetime
from src.quant.reproducibility import (
    ResearchRunIdentity, DatasetVersionLock, ResearchInputManifest, ResearchResultManifest,
    ResearchRunStore, ResearchReplayEngine, ReplayStatus, compute_canonical_sha256
)
from src.quant.backtest.engine import BacktestEngine
from src.quant.portfolio.construction import PortfolioTarget
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.revision.revision_store import RevisionStore
from src.data.revision.revision_model import DataRevision


def _setup_fixture(tmp_dir: str):
    store = RevisionStore()
    rev = DataRevision(
        record_id="r1", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1600.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0), revision_id="rev_1", dataset_version="ds_v1.0"
    )
    store.add_revision(rev)

    mgr = SnapshotManager(revision_store=store)
    snap = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_lock_01", dataset_version="ds_v1.0")

    run_store = ResearchRunStore(base_dir=tmp_dir)
    return store, mgr, snap, run_store


def test_1_replay_same_run_is_identical(tmp_path):
    store, mgr, snap, run_store = _setup_fixture(str(tmp_path))

    prices = {"600519.SH": [1600.0, 1620.0]}
    targets = [PortfolioTarget("2022-05-01", "strat_mom", {"600519.SH": 1.0}, 1.0)]

    engine = BacktestEngine()
    bt_res = engine.run_backtest("ds_v1.0", "strat_mom", prices, targets, snapshot_id="snap_lock_01", as_of=datetime(2022, 5, 2))

    res_payload = {"sharpe": bt_res.sharpe_ratio, "return": bt_res.total_return, "mdd": bt_res.max_drawdown}
    res_hash = compute_canonical_sha256(res_payload)

    input_manifest = ResearchInputManifest(
        research_run_id="run_101", dataset_id="golden_ds", dataset_version="ds_v1.0",
        snapshot_id="snap_lock_01", dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00",
        start_date="2022-05-01", end_date="2022-05-02", universe_type="A_SHARE",
        universe_symbols=["600519.SH"], universe_hash="u_hash",
        factors_config=[{"factor": "momentum_20d:v1", "weight": 1.0}],
        factor_definition_hash="f_hash_v1", strategy_id="strat_mom", strategy_version="1.0.0",
        strategy_parameters={"top_n": 1}, parameter_hash="p_hash_v1",
        portfolio_constraints={"max_w": 1.0}, cost_model_config={"commission": 0.0003},
        transaction_cost_model_hash="c_hash_v1", benchmark_id="000300.SH",
        benchmark_version="1.0", benchmark_hash="b_hash", code_version="45ad1ba",
        code_state="CLEAN", created_at="2022-05-02T10:00:00"
    )
    input_hash = input_manifest.compute_input_hash()

    result_manifest = ResearchResultManifest(
        research_run_id="run_101", input_manifest_hash=input_hash, result_hash=res_hash,
        equity_curve_hash=res_hash
    )

    identity = ResearchRunIdentity(
        research_run_id="run_101", snapshot_id="snap_lock_01", dataset_version="ds_v1.0",
        dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00", start_date="2022-05-01",
        end_date="2022-05-02", universe_definition={"symbols": ["600519.SH"]}, universe_hash="u_hash",
        strategy_id="strat_mom", strategy_version="1.0.0", factor_definition_hash="f_hash_v1",
        parameter_hash="p_hash_v1", transaction_cost_model_hash="c_hash_v1", benchmark_id="000300.SH",
        code_version="45ad1ba", code_state="CLEAN", input_hash=input_hash, result_hash=res_hash,
        created_at="2022-05-02T10:00:00"
    )

    run_store.create_run(identity, input_manifest, result_manifest, {"daily_prices": prices})

    replay_engine = ResearchReplayEngine(run_store=run_store, snapshot_manager=mgr, backtest_engine=engine)
    report = replay_engine.replay_run("run_101")

    assert report.status == ReplayStatus.REPRODUCIBLE
    assert report.original_result_hash == report.replayed_result_hash


def test_2_modified_dataset_version_cannot_replay_as_same(tmp_path):
    store, mgr, snap, run_store = _setup_fixture(str(tmp_path))

    with pytest.raises(ValueError, match="FAIL CLOSED"):
        DatasetVersionLock.lock(dataset_version="ds_NON_EXISTENT", snapshot_id="snap_lock_01", snapshot_manager=mgr)


def test_3_modified_factor_version_changes_identity():
    f1_hash = compute_canonical_sha256([{"factor": "momentum_20d:v1"}])
    f2_hash = compute_canonical_sha256([{"factor": "momentum_20d:v2"}])
    assert f1_hash != f2_hash


def test_4_modified_strategy_parameter_changes_identity():
    p1_hash = compute_canonical_sha256({"top_n": 1})
    p2_hash = compute_canonical_sha256({"top_n": 2})
    assert p1_hash != p2_hash


def test_5_modified_transaction_cost_changes_identity():
    c1_hash = compute_canonical_sha256({"commission": 0.0003})
    c2_hash = compute_canonical_sha256({"commission": 0.0005})
    assert c1_hash != c2_hash


def test_6_modified_universe_changes_identity():
    u1_hash = compute_canonical_sha256(["600519.SH"])
    u2_hash = compute_canonical_sha256(["600519.SH", "000001.SZ"])
    assert u1_hash != u2_hash


def test_7_modified_snapshot_changes_identity():
    s1_hash = compute_canonical_sha256({"snapshot_id": "snap_v1"})
    s2_hash = compute_canonical_sha256({"snapshot_id": "snap_v2"})
    assert s1_hash != s2_hash
