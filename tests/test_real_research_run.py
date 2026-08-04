"""
test_real_research_run.py — Real historical research run execution & identity creation tests.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine
from src.quant.reproducibility.store import ResearchRunStore


def test_real_research_run_creation(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    run_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))

    audit_out = engine.run_end_to_end_replay_verification(snap_mgr, run_store)

    assert audit_out["research_run_id"] == "real_research_run_2022_2024"
    assert audit_out["original_result_hash"] != ""
    assert audit_out["replay_status"] == "REPRODUCIBLE"
