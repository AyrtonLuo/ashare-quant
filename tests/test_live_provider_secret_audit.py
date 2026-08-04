"""
test_live_provider_secret_audit.py — Zero secret leakage security audit test.
"""

import pytest
from src.data.security.secret_audit import SecurityAuditManager
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


def test_live_provider_secret_audit_execution(tmp_path):
    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    _ = engine.execute_phase_7g_certification(run_store_dir=str(tmp_path / "runs"))

    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))

    assert res["status"] == "PASSED"
    assert len(res["leaked_secrets"]) == 0
