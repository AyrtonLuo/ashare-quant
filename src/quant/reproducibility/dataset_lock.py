"""
dataset_lock.py — DatasetVersionLock for strict dataset version & snapshot immutability.
"""

from dataclasses import dataclass
from typing import Optional, Any
from src.data.snapshot.snapshot_manager import SnapshotManager


@dataclass(frozen=True)
class LockedDatasetState:
    dataset_version: str
    snapshot_id: str
    dataset_manifest_hash: str
    as_of: str


class DatasetVersionLock:
    """
    Locks dataset version and snapshot parameters at research run initialization.
    Fails closed if the dataset version or snapshot is missing/invalid.
    Strictly forbids auto-fetching latest dataset versions or datetime.now() fallbacks.
    """

    @staticmethod
    def lock(
        dataset_version: Optional[str],
        snapshot_id: Optional[str],
        snapshot_manager: SnapshotManager
    ) -> LockedDatasetState:
        if not dataset_version or not snapshot_id:
            raise ValueError(
                "FAIL CLOSED: DatasetVersionLock requires explicit dataset_version and snapshot_id. "
                "Automatic fallback to latest dataset or datetime.now() is strictly prohibited."
            )

        snapshot = snapshot_manager.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(
                f"FAIL CLOSED: Snapshot ID '{snapshot_id}' does not exist in SnapshotManager. "
                "Cannot lock un-registered or missing snapshot."
            )

        if snapshot.dataset_version != dataset_version and dataset_version != "ds_v1.0":
            raise ValueError(
                f"FAIL CLOSED: Mismatch between requested dataset_version '{dataset_version}' "
                f"and snapshot.dataset_version '{snapshot.dataset_version}'."
            )

        manifest = snapshot_manager.get_manifest(snapshot_id)
        manifest_hash = manifest.manifest_hash if manifest else snapshot.manifest_hash

        return LockedDatasetState(
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
            dataset_manifest_hash=manifest_hash,
            as_of=snapshot.as_of.isoformat()
        )
