"""
test_real_dataset_cross_provider.py — Cross-provider data validation tests.
Decorated with @pytest.mark.real_data.
"""

import pytest
from src.data.providers.tushare_provider import TuShareAdapter
from src.data.providers.akshare_provider import AkShareProviderAdapter
from src.data.warehouse.real_data_verifier import check_provider_credentials


@pytest.mark.real_data
def test_cross_provider_validation_if_available():
    creds = check_provider_credentials()
    if not creds["has_tushare"] or not creds["has_akshare"]:
        pytest.skip("REAL_DATA_CREDENTIALS_UNAVAILABLE: Skipping live cross-provider test.")

    primary = TuShareAdapter()
    secondary = AkShareProviderAdapter()

    m1 = primary.fetch_market_data("600519.SH", "2022-05-01")
    m2 = secondary.fetch_market_data("600519.SH", "2022-05-01")

    assert m1 is not None
    assert m2 is not None
    assert m1.symbol == m2.symbol
