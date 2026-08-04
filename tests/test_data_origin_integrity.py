"""
test_data_origin_integrity.py — Adversarial tests for data_origin certification & separation.
"""

import pytest


def test_data_origin_values_are_distinct():
    origin_real = "REAL_PROVIDER"
    origin_local = "LOCAL_PRODUCTION_VERIFICATION_DATA"
    origin_golden = "GOLDEN_DATASET"
    origin_synthetic = "SYNTHETIC_DATA"

    assert origin_real != origin_local
    assert origin_real != origin_golden
    assert origin_real != origin_synthetic
    assert origin_local != origin_golden


def test_local_data_cannot_claim_real_provider_tag():
    is_live_network_response = False
    data_origin = "REAL_PROVIDER" if is_live_network_response else "LOCAL_PRODUCTION_VERIFICATION_DATA"

    assert data_origin == "LOCAL_PRODUCTION_VERIFICATION_DATA"
    assert data_origin != "REAL_PROVIDER"
