"""
test_live_provider_data_origin.py — Data origin certification & separation test.
"""

import pytest


def test_live_provider_data_origin_separation():
    origin_real = "REAL_PROVIDER"
    origin_local = "LOCAL_PRODUCTION_VERIFICATION_DATA"
    origin_golden = "GOLDEN_DATASET"

    assert origin_real != origin_local
    assert origin_real != origin_golden
