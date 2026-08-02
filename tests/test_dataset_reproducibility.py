"""
test_dataset_reproducibility.py — Tests verifying Historical Dataset Reproducibility.
"""

from src.data.domain.manifest import DatasetManifestManager


def test_reproducibility_hash_consistency():
    dataset_a = [{"symbol": "600519.SH", "price": 1650.0}]
    dataset_b = [{"symbol": "600519.SH", "price": 1650.0}]
    
    hash_a = DatasetManifestManager.compute_sha256(dataset_a)
    hash_b = DatasetManifestManager.compute_sha256(dataset_b)

    assert hash_a == hash_b, "Identical datasets must yield identical SHA-256 hashes for 100% reproducibility"
