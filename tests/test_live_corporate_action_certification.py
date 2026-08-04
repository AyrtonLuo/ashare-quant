"""
test_live_corporate_action_certification.py — Live corporate action certification test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_corporate_action_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7f_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "corporate_action_certification.json").exists()
