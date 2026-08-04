"""
test_live_provider_credentialed.py — Live provider credentialed verification test.
Decorated with @pytest.mark.real_provider.
"""

import pytest
from src.quant.providers.preflight import ProviderCredentialPreflight
from src.data.warehouse.live_provider_verifier import LiveProviderVerificationEngine


@pytest.mark.real_provider
def test_live_provider_credentialed_execution(tmp_path):
    preflight = ProviderCredentialPreflight.inspect_tushare_credentials()
    if preflight["credential_status"] != "AVAILABLE":
        pytest.skip("LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE: TUSHARE_TOKEN not available in environment.")

    engine = LiveProviderVerificationEngine(audit_dir=str(tmp_path))
    res = engine.execute_phase_7g_certification(run_store_dir=str(tmp_path / "runs"))

    assert res["is_live_provider_available"] is True
    # NOTE: credential availability alone does not make the certified dataset REAL_PROVIDER —
    # this pipeline still seeds its dataset from a synthetic fixture (see Phase 7H
    # specification). data_origin only becomes REAL_PROVIDER once a genuine live-fetch dataset
    # path replaces the formula-generated one.
    assert res["data_origin"] == "SYNTHETIC_DATA"
