"""
test_real_dataset_manifest.py — Real dataset manifest generation & SHA-256 verification tests.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine, VERIFICATION_SYMBOLS


def test_real_dataset_manifest_generation(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset(
        dataset_id="real_historical_dataset_v1",
        symbols=VERIFICATION_SYMBOLS,
        start_date="2021-01-01",
        end_date="2024-12-31"
    )

    assert manifest.dataset_id == "real_historical_dataset_v1"
    assert manifest.symbol_count == 20
    assert manifest.start_date == "2021-01-01"
    assert manifest.end_date == "2024-12-31"
    assert manifest.checksum_sha256 != ""
