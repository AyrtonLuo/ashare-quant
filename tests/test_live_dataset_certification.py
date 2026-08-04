"""
test_live_dataset_certification.py — Live dataset certification audit test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_dataset_certification_execution(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    res = engine.execute_phase_7e_certification(run_store_dir=str(tmp_path / "runs"))

    assert res["verdict"] in ["PASS", "PASS_WITH_LIMITATIONS"]
    assert (tmp_path / "dataset_certification.json").exists()
