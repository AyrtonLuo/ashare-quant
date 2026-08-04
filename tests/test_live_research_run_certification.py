"""
test_live_research_run_certification.py — Live research run certification test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_research_run_certification(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7f_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "research_run_certification.json").exists()
