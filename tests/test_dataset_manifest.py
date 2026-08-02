"""
test_dataset_manifest.py — Tests for Dataset Manifest & SHA-256 Checksums.
"""

from src.data.domain.manifest import DatasetManifestManager


def test_dataset_manifest_creation_and_verification():
    payload = [{"symbol": "600519.SH", "close": 1650.0}, {"symbol": "000001.SZ", "close": 11.5}]
    
    manifest = DatasetManifestManager.create_manifest(
        dataset_id="golden_test_v1",
        created_at="2026-08-02T00:00:00Z",
        primary_source="tushare_pro_primary",
        secondary_source="akshare_secondary",
        schema_version="1.0.0",
        start_date="2020-01-01",
        end_date="2026-08-01",
        symbol_count=2,
        row_count=2,
        data_payload=payload
    )

    assert manifest.symbol_count == 2
    assert DatasetManifestManager.verify_manifest(manifest, payload) is True
    
    # Tampered payload fails verification!
    tampered = [{"symbol": "600519.SH", "close": 9999.0}]
    assert DatasetManifestManager.verify_manifest(manifest, tampered) is False
