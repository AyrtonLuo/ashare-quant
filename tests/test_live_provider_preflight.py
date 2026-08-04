"""
test_live_provider_preflight.py — Audit test for ProviderCredentialPreflight credential detection & safety.
"""

import pytest
from src.data.providers.preflight import ProviderCredentialPreflight


def test_credential_preflight_runs_safely(tmp_path):
    report = ProviderCredentialPreflight.run_preflight_audit(audit_dir=str(tmp_path))

    assert "preflight_status" in report
    assert report["preflight_status"] in ["AVAILABLE", "UNAVAILABLE", "INVALID", "API_UNREACHABLE"]
    # Verify zero secrets in output dictionary
    for k, v in report.items():
        assert "token" not in str(v).lower() or "unavailable" in str(v).lower()
