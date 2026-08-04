"""
test_no_secret_leakage.py — Audit test verifying zero secret leakage in logs, manifests, and audit JSON files.
"""

import pytest
from src.data.security.secret_audit import SecurityAuditManager
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_zero_secret_leakage_in_audit_artifacts(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7f_certification(run_store_dir=str(tmp_path / "runs"))

    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))

    assert res["status"] == "PASSED"
    assert len(res["leaked_secrets"]) == 0
    assert res["security_certification"] == "CERTIFIED_ZERO_SECRET_LEAKAGE"
