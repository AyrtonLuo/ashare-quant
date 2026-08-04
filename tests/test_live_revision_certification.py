"""
test_live_revision_certification.py — Live revision lineage certification test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_revision_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7e_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "revision_certification.json").exists()
