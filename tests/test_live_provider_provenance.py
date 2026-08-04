"""
test_live_provider_provenance.py — Live provider provenance metadata verification test.
Decorated with @pytest.mark.real_provider.
"""

import pytest
from src.data.providers.preflight import ProviderCredentialPreflight
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


@pytest.mark.real_provider
def test_live_provider_provenance_tagging(tmp_path):
    preflight = ProviderCredentialPreflight.inspect_tushare_credentials()
    if preflight["credential_status"] != "AVAILABLE":
        pytest.skip("LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE: TUSHARE_TOKEN not available in environment.")

    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    res = engine.execute_live_verification_pipeline(run_store_dir=str(tmp_path / "runs"))

    # NOTE: credential availability alone does not make the certified dataset verified-real —
    # this pipeline still seeds its dataset from a synthetic fixture (see Phase 7H
    # specification) until a genuine live-fetch dataset path replaces it.
    assert res["provenance_status"] == "NOT_VERIFIED_SYNTHETIC_FIXTURE_PIPELINE"
