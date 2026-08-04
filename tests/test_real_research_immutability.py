"""
test_real_research_immutability.py — Research run immutability tests on real datasets.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine
from src.quant.reproducibility.store import ResearchRunStore


def test_real_research_run_cannot_be_overwritten(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    run_store = ResearchRunStore(base_dir=str(tmp_path / "runs"))

    _ = engine.run_end_to_end_replay_verification(snap_mgr, run_store)

    run_data = run_store.get_run("real_research_run_2022_2024")
    assert run_data is not None

    with pytest.raises(ValueError, match="already exists and is IMMUTABLE"):
        run_store.create_run(
            run_data["identity"],
            run_data["input_manifest"],
            run_data["result_manifest"]
        )
