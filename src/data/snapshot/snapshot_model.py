"""
snapshot_model.py — DataSnapshot & SnapshotManifest Data Structures.
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class DataSnapshot:
    """
    Logical point-in-time snapshot representing the state of the data world at `as_of`.
    """
    snapshot_id: str
    as_of: datetime
    dataset_version: str
    provider_versions: Dict[str, str]
    data_cutoff: datetime
    created_at: datetime
    schema_version: str
    manifest_hash: str


@dataclass(frozen=True)
class SnapshotManifest:
    """
    Comprehensive cryptographic manifest for 100% reproducible data snapshots.
    """
    snapshot_id: str
    dataset_manifest_hash: str
    schema_hash: str
    provider_manifest: Dict[str, Any]
    revision_policy: str
    as_of: datetime
    created_at: datetime
    code_version: str
    parameter_hash: str
    manifest_hash: str


class SnapshotManifestBuilder:
    """Helper to compute deterministic SHA-256 hashes and build SnapshotManifest."""

    @staticmethod
    def compute_hash(payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    @classmethod
    def create_manifest(
        cls,
        snapshot_id: str,
        as_of: datetime,
        dataset_version: str,
        provider_versions: Dict[str, str],
        revision_policy: str = "POINT_IN_TIME_LATEST",
        code_version: str = "1.0.0",
        schema_version: str = "1.0.0",
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[DataSnapshot, SnapshotManifest]:
        created_at = datetime.now()
        data_cutoff = as_of

        dataset_manifest_hash = cls.compute_hash({"dataset_version": dataset_version, "as_of": as_of})
        schema_hash = cls.compute_hash({"schema_version": schema_version})
        provider_manifest = provider_versions
        parameter_hash = cls.compute_hash(parameters or {})

        manifest_payload = {
            "snapshot_id": snapshot_id,
            "dataset_manifest_hash": dataset_manifest_hash,
            "schema_hash": schema_hash,
            "provider_manifest": provider_manifest,
            "revision_policy": revision_policy,
            "as_of": as_of.isoformat(),
            "code_version": code_version,
            "parameter_hash": parameter_hash,
        }
        manifest_hash = cls.compute_hash(manifest_payload)

        snapshot = DataSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            dataset_version=dataset_version,
            provider_versions=provider_versions,
            data_cutoff=data_cutoff,
            created_at=created_at,
            schema_version=schema_version,
            manifest_hash=manifest_hash
        )

        manifest = SnapshotManifest(
            snapshot_id=snapshot_id,
            dataset_manifest_hash=dataset_manifest_hash,
            schema_hash=schema_hash,
            provider_manifest=provider_manifest,
            revision_policy=revision_policy,
            as_of=as_of,
            created_at=created_at,
            code_version=code_version,
            parameter_hash=parameter_hash,
            manifest_hash=manifest_hash
        )

        return snapshot, manifest
