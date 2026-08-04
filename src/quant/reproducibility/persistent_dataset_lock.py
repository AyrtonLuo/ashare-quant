"""
persistent_dataset_lock.py — Locks a research run to a REAL, on-disk, checksummed dataset
artifact (as opposed to dataset_lock.py's DatasetVersionLock, which binds to a snapshot's
declared dataset_version string without proving any file exists on disk).

Fails closed on: uncertified dataset, missing artifact, corrupted artifact, or content hash
mismatch (artifact modified after certification). Never resolves "latest" or "current" —
callers must supply an explicit dataset_id/dataset_version pair.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from src.data.domain.persistent_manifest import (
    PersistentDatasetManifestManager,
    PersistentDatasetManifestStore,
)


@dataclass(frozen=True)
class LockedPersistentDatasetState:
    dataset_id: str
    dataset_version: str
    artifact_path: str
    content_sha256: str
    row_count: int


class PersistentDatasetLock:
    @staticmethod
    def lock(
        dataset_id: str,
        dataset_version: str,
        directory: Union[str, Path],
        manifest_store: PersistentDatasetManifestStore,
    ) -> LockedPersistentDatasetState:
        if not dataset_id or not dataset_version:
            raise ValueError(
                "FAIL CLOSED: PersistentDatasetLock requires explicit dataset_id and "
                "dataset_version. Automatic fallback to 'latest' is strictly prohibited."
            )

        expected = manifest_store.get(dataset_id, dataset_version)
        if expected is None:
            raise ValueError(
                f"FAIL CLOSED: no certified manifest found for dataset_id='{dataset_id}' "
                f"dataset_version='{dataset_version}'. Cannot lock an uncertified dataset."
            )

        directory = Path(directory)
        if not directory.exists() or not any(directory.glob("*.parquet")):
            raise FileNotFoundError(
                f"FAIL CLOSED: persistent dataset artifact missing at '{directory}' for "
                f"dataset_id='{dataset_id}' dataset_version='{dataset_version}'. Cannot "
                "replay or research against a dataset whose artifact no longer exists."
            )

        recomputed = PersistentDatasetManifestManager.build_manifest(
            dataset_id, dataset_version, directory, expected.created_at
        )
        if recomputed.content_sha256 != expected.content_sha256:
            raise ValueError(
                f"FAIL CLOSED: content hash mismatch for dataset_id='{dataset_id}' "
                f"dataset_version='{dataset_version}'. Expected content_sha256="
                f"'{expected.content_sha256}', found '{recomputed.content_sha256}'. The "
                "artifact was modified or corrupted after certification."
            )

        return LockedPersistentDatasetState(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            artifact_path=str(directory),
            content_sha256=recomputed.content_sha256,
            row_count=recomputed.row_count,
        )
