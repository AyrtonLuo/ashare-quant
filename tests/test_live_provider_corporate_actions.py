"""
test_live_provider_corporate_actions.py — Corporate action temporal binding test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_provider_corporate_action_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7g_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "live_corporate_action_certification.json").exists()
