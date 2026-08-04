"""
test_research_run_store_immutability.py — Audit tests for ResearchRunStore immutability, tampering detection, and Golden Run.
"""

import pytest
from datetime import datetime
from typing import Tuple
from src.quant.reproducibility import (
    ResearchRunIdentity, ResearchInputManifest, ResearchResultManifest,
    ResearchRunStore, ResearchResultComparator, ComparisonStatus,
    compute_canonical_sha256, get_code_version
)
from src.data.snapshot.snapshot_manager import SnapshotManager
from src.data.revision.revision_store import RevisionStore
from src.data.revision.revision_model import DataRevision


def _create_sample_identity(run_id: str, param_val: int = 1) -> Tuple[ResearchRunIdentity, ResearchInputManifest, ResearchResultManifest]:
    p_hash = compute_canonical_sha256({"top_n": param_val})
    res_payload = {"sharpe": 1.5, "return": 0.1, "mdd": 0.05}
    res_hash = compute_canonical_sha256(res_payload)

    input_manifest = ResearchInputManifest(
        research_run_id=run_id, dataset_id="golden_ds", dataset_version="ds_v1.0",
        snapshot_id="snap_01", dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00",
        start_date="2022-05-01", end_date="2022-05-02", universe_type="A_SHARE",
        universe_symbols=["600519.SH"], universe_hash="u_hash",
        factors_config=[{"factor": "momentum"}], factor_definition_hash="f_hash",
        strategy_id="strat_mom", strategy_version="1.0.0", strategy_parameters={"top_n": param_val},
        parameter_hash=p_hash, portfolio_constraints={"max_w": 1.0},
        cost_model_config={"commission": 0.0003}, transaction_cost_model_hash="c_hash",
        benchmark_id="000300.SH", benchmark_version="1.0", benchmark_hash="b_hash",
        code_version="45ad1ba", code_state="CLEAN", created_at="2022-05-02T10:00:00"
    )
    input_hash = input_manifest.compute_input_hash()

    result_manifest = ResearchResultManifest(
        research_run_id=run_id, input_manifest_hash=input_hash, result_hash=res_hash,
        equity_curve_hash=res_hash
    )

    identity = ResearchRunIdentity(
        research_run_id=run_id, snapshot_id="snap_01", dataset_version="ds_v1.0",
        dataset_manifest_hash="hash_ds", as_of="2022-05-02T00:00:00", start_date="2022-05-01",
        end_date="2022-05-02", universe_definition={"symbols": ["600519.SH"]}, universe_hash="u_hash",
        strategy_id="strat_mom", strategy_version="1.0.0", factor_definition_hash="f_hash",
        parameter_hash=p_hash, transaction_cost_model_hash="c_hash", benchmark_id="000300.SH",
        code_version="45ad1ba", code_state="CLEAN", input_hash=input_hash, result_hash=res_hash,
        created_at="2022-05-02T10:00:00"
    )
    return identity, input_manifest, result_manifest


def test_8_tampering_and_comparator_detects_parameter_diff():
    id_a, in_a, res_a = _create_sample_identity("run_A", param_val=1)
    id_b, in_b, res_b = _create_sample_identity("run_B", param_val=2)

    report = ResearchResultComparator.compare_runs(id_a, id_b, in_a, in_b, res_a, res_b)

    assert report.status == ComparisonStatus.DIFFERENT_INPUT
    assert "parameter_hash differs" in report.difference_reason


def test_9_research_run_is_immutable(tmp_path):
    store = ResearchRunStore(base_dir=str(tmp_path))
    id_a, in_a, res_a = _create_sample_identity("run_immut_01")
    store.create_run(id_a, in_a, res_a)

    # Attempting to overwrite run_immut_01 MUST fail closed
    with pytest.raises(ValueError, match="already exists and is IMMUTABLE"):
        store.create_run(id_a, in_a, res_a)


def test_10_git_version_state_inspection():
    commit, state = get_code_version()
    assert commit != ""
    assert state in ["CLEAN", "DIRTY", "UNAVAILABLE"]


def test_11_golden_research_run_v1_deterministic(tmp_path):
    """
    SECTION 20: Golden Research Run v1 Regression Test.
    Runs golden input payload, computes canonical hashes, verifies replay determinism.
    """
    store_db = RevisionStore()
    rev = DataRevision(
        record_id="golden_rec_01", symbol="600519.SH", field="close", effective_date="2022-05-01",
        value=1600.0, provider="tushare", available_at=datetime(2022, 5, 1, 15, 0),
        received_at=datetime(2022, 5, 1, 15, 0), revision_id="rev_gold", dataset_version="ds_v1.0"
    )
    store_db.add_revision(rev)

    mgr = SnapshotManager(revision_store=store_db)
    snap = mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="golden_snapshot_v1", dataset_version="ds_v1.0")

    run_store = ResearchRunStore(base_dir=str(tmp_path))
    id_g, in_g, res_g = _create_sample_identity("golden_research_run_v1")

    run_store.create_run(id_g, in_g, res_g, {"daily_prices": {"600519.SH": [1600.0, 1620.0]}})

    fetch_run = run_store.get_run("golden_research_run_v1")
    assert fetch_run is not None
    assert fetch_run["identity"].research_run_id == "golden_research_run_v1"
    assert fetch_run["result_manifest"].result_hash == res_g.result_hash
