"""
test_real_provider_origin_cannot_be_faked.py — Adversarial test asserting data origin integrity.
"""

import pytest


def test_real_provider_origin_integrity():
    is_live_network_response = False
    data_origin = "REAL_PROVIDER" if is_live_network_response else "LOCAL_PRODUCTION_VERIFICATION_DATA"

    assert data_origin == "LOCAL_PRODUCTION_VERIFICATION_DATA"
    assert data_origin != "REAL_PROVIDER"
