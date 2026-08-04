"""
test_live_immutability.py — Live research run immutability test.
"""

import pytest
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_research_run_immutability(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7e_certification(run_store_dir=str(tmp_path / "runs"))

    assert (tmp_path / "immutability_report.json").exists()
