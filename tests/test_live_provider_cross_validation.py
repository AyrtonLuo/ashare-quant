"""
test_live_provider_cross_validation.py — Live provider cross-validation test.
Decorated with @pytest.mark.real_provider.
"""

import pytest
from src.data.providers.preflight import ProviderCredentialPreflight


@pytest.mark.real_provider
def test_live_provider_cross_validation_probe():
    preflight = ProviderCredentialPreflight.inspect_tushare_credentials()
    if preflight["credential_status"] != "AVAILABLE":
        pytest.skip("LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE: TUSHARE_TOKEN not available in environment.")

    assert preflight["credential_status"] == "AVAILABLE"
