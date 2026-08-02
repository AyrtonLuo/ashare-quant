"""
test_dataset_versioning.py — Tests verifying dataset versioning & non-overwriting.
"""

from src.data.domain.manifest import DatasetManifestManager


def test_dataset_versioning_manifest():
    payload_v1 = [{"symbol": "600519.SH", "v": 1}]
    payload_v2 = [{"symbol": "600519.SH", "v": 2}]

    m1 = DatasetManifestManager.create_manifest(
        "ds_v1", "2026-08-01", "tushare", "akshare", "1.0.0", "2020-01-01", "2026-08-01", 1, 1, payload_v1
    )
    m2 = DatasetManifestManager.create_manifest(
        "ds_v2", "2026-08-02", "tushare", "akshare", "1.1.0", "2020-01-01", "2026-08-02", 1, 1, payload_v2
    )

    assert m1.dataset_id != m2.dataset_id
    assert m1.checksum_sha256 != m2.checksum_sha256
