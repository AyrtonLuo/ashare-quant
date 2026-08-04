"""
test_live_provider_dataset_manifest.py — Live provider dataset manifest test.
Decorated with @pytest.mark.real_provider.
"""

import pytest
from src.data.providers.preflight import ProviderCredentialPreflight
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


@pytest.mark.real_provider
def test_live_provider_dataset_manifest(tmp_path):
    preflight = ProviderCredentialPreflight.inspect_tushare_credentials()
    if preflight["credential_status"] != "AVAILABLE":
        pytest.skip("LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE: TUSHARE_TOKEN not available in environment.")

    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    res = engine.execute_live_verification_pipeline(run_store_dir=str(tmp_path / "runs"))

    assert res["preflight_status"] == "AVAILABLE"
