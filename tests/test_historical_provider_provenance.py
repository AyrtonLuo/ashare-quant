"""
test_historical_provider_provenance.py — Tests verifying provider lineage tags in Warehouse.
"""

from src.data.providers.tushare_provider import TuShareAdapter


def test_provider_provenance_id():
    adapter = TuShareAdapter()
    assert adapter.provider_id == "tushare_pro_primary"
    assert adapter.provider_version == "1.2.89"
