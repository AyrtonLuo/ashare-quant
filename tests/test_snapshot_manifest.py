"""
test_snapshot_manifest.py — Tests for DataSnapshot & SnapshotManifest creation and verification.
"""

from datetime import datetime
from src.data.snapshot.snapshot_model import SnapshotManifestBuilder, DataSnapshot, SnapshotManifest


def test_snapshot_manifest_creation_and_hashing():
    as_of_dt = datetime(2022, 8, 1, 15, 0, 0)
    snapshot, manifest = SnapshotManifestBuilder.create_manifest(
        snapshot_id="snapshot_20220801_v1",
        as_of=as_of_dt,
        dataset_version="ds_v1.0",
        provider_versions={"tushare": "2.0", "akshare": "1.0"},
        revision_policy="POINT_IN_TIME_LATEST",
        code_version="1.0.0",
        schema_version="1.0.0",
        parameters={"factor": "momentum"}
    )

    assert isinstance(snapshot, DataSnapshot)
    assert isinstance(manifest, SnapshotManifest)
    assert snapshot.snapshot_id == "snapshot_20220801_v1"
    assert snapshot.as_of == as_of_dt
    assert snapshot.dataset_version == "ds_v1.0"
    assert manifest.dataset_manifest_hash != ""
    assert manifest.manifest_hash == snapshot.manifest_hash
