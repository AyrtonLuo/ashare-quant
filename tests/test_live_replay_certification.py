"""
test_live_replay_certification.py — Live research replay determinism certification test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_replay_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    res = engine.execute_phase_7f_certification(run_store_dir=str(tmp_path / "runs"))

    assert res["replay_status"] == "REPRODUCIBLE"
    assert (tmp_path / "replay_certification.json").exists()
