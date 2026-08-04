"""
test_real_research_replay.py — Production-scale research run replay & result hash match tests.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine
from src.quant.reproducibility.store import ResearchRunStore
from src.quant.reproducibility.replay_engine import ResearchReplayEngine, ReplayStatus


def test_real_research_run_replay_determinism(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    run_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))

    _ = engine.run_end_to_end_replay_verification(snap_mgr, run_store)

    replay_engine = ResearchReplayEngine(run_store=run_store, snapshot_manager=snap_mgr)
    report = replay_engine.replay_run("real_research_run_2022_2024")

    assert report.status == ReplayStatus.REPRODUCIBLE
    assert report.original_result_hash == report.replayed_result_hash
