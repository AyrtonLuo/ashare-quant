"""
test_live_snapshot_certification.py — Live PIT snapshot certification test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_snapshot_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7e_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "snapshot_certification.json").exists()
