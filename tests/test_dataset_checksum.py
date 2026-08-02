"""
test_dataset_checksum.py — Tests verifying SHA-256 binary hash integrity.
"""

from src.data.domain.manifest import DatasetManifestManager


def test_dataset_checksum_tamper_detection():
    data = {"symbols": ["600519.SH"], "price": 1650.0}
    manifest = DatasetManifestManager.create_manifest(
        "check_ds", "2026-08-01", "tushare", "akshare", "1.0.0", "2026-08-01", "2026-08-01", 1, 1, data
    )

    assert DatasetManifestManager.verify_manifest(manifest, data) is True

    corrupted_data = {"symbols": ["600519.SH"], "price": 1651.0}
    assert DatasetManifestManager.verify_manifest(manifest, corrupted_data) is False
