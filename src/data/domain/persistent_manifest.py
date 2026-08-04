"""
persistent_manifest.py — Manifest binding for REAL, on-disk persisted datasets.

Unlike DatasetManifestManager (manifest.py), which hashes an in-memory Python payload,
PersistentDatasetManifestManager hashes the actual bytes of Parquet files that exist on disk
under a dataset directory. A manifest produced here is proof that a specific set of file
bytes existed at certification time — it cannot be satisfied by any in-memory-only structure.

PersistentDatasetManifestStore is an immutable registry: once a (dataset_id, dataset_version)
pair is certified with a given content hash, no different content may ever be certified under
that same version string. This is what makes "dataset_version" a trustworthy identity for a
persistent artifact rather than just a label.
"""

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from src.quant.reproducibility.canonical import to_canonical_json


@dataclass(frozen=True)
class PersistentDatasetManifest:
    dataset_id: str
    dataset_version: str
    artifact_path: str
    artifact_type: str          # "PARQUET"
    file_size: int              # total bytes across all Parquet files in the directory
    created_at: str
    schema_hash: str
    content_sha256: str         # hash of actual on-disk file bytes, not any in-memory repr
    row_count: int
    min_trading_date: str
    max_trading_date: str
    symbols: List[str]
    universe_hash: str


class PersistentDatasetManifestManager:
    ARTIFACT_TYPE = "PARQUET"

    @staticmethod
    def _hash_file_bytes(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def build_manifest(
        cls, dataset_id: str, dataset_version: str, directory: Path, created_at: str
    ) -> PersistentDatasetManifest:
        """Reads real Parquet files from `directory` and hashes their actual bytes. Fails
        closed if the directory is missing, empty, unreadable, or has inconsistent schemas —
        never falls back to certifying an empty or partial dataset as if it were complete."""
        import pandas as pd

        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            raise FileNotFoundError(
                f"FAIL CLOSED: dataset directory '{directory}' does not exist. Cannot certify "
                "a persistent dataset that was never written to disk."
            )

        parquet_files = sorted(directory.glob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(
                f"FAIL CLOSED: dataset directory '{directory}' contains zero Parquet files. "
                "Cannot certify an empty persistent dataset."
            )

        combined_hasher = hashlib.sha256()
        total_size = 0
        total_rows = 0
        all_symbols = set()
        min_date: Optional[str] = None
        max_date: Optional[str] = None
        schema_signature: Optional[str] = None

        for fp in parquet_files:  # sorted -> deterministic hash regardless of filesystem order
            try:
                df = pd.read_parquet(fp)
            except Exception as e:
                raise ValueError(
                    f"FAIL CLOSED: could not read Parquet file '{fp}' — artifact may be "
                    f"corrupted: {e}"
                )

            file_hash = cls._hash_file_bytes(fp)
            combined_hasher.update(fp.name.encode("utf-8"))
            combined_hasher.update(file_hash.encode("utf-8"))

            total_size += fp.stat().st_size
            total_rows += len(df)

            if "symbol" in df.columns:
                all_symbols.update(df["symbol"].unique().tolist())
            if "trading_date" in df.columns and len(df) > 0:
                file_min = str(df["trading_date"].min())
                file_max = str(df["trading_date"].max())
                min_date = file_min if min_date is None or file_min < min_date else min_date
                max_date = file_max if max_date is None or file_max > max_date else max_date

            col_signature = ",".join(sorted(df.columns))
            if schema_signature is None:
                schema_signature = col_signature
            elif schema_signature != col_signature:
                raise ValueError(
                    f"FAIL CLOSED: schema mismatch across Parquet files in '{directory}': "
                    f"'{fp.name}' has columns [{col_signature}] but expected [{schema_signature}]."
                )

        content_sha256 = combined_hasher.hexdigest()
        schema_hash = hashlib.sha256((schema_signature or "").encode("utf-8")).hexdigest()
        universe_hash = hashlib.sha256(",".join(sorted(all_symbols)).encode("utf-8")).hexdigest()

        return PersistentDatasetManifest(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            artifact_path=str(directory),
            artifact_type=cls.ARTIFACT_TYPE,
            file_size=total_size,
            created_at=created_at,
            schema_hash=schema_hash,
            content_sha256=content_sha256,
            row_count=total_rows,
            min_trading_date=min_date or "",
            max_trading_date=max_date or "",
            symbols=sorted(all_symbols),
            universe_hash=universe_hash,
        )

    @classmethod
    def verify(cls, manifest: PersistentDatasetManifest) -> bool:
        """Recomputes the manifest from the artifact currently on disk and compares content_sha256."""
        recomputed = cls.build_manifest(
            manifest.dataset_id, manifest.dataset_version, Path(manifest.artifact_path), manifest.created_at
        )
        return recomputed.content_sha256 == manifest.content_sha256


class PersistentDatasetManifestStore:
    """Immutable registry: a (dataset_id, dataset_version) pair identifies exactly one content
    hash. Certifying different content under an already-used version string fails closed
    instead of silently overwriting the prior identity.

    With no `base_dir`, this immutability guarantee holds only for the lifetime of the Python
    object — a fresh instance has no memory of prior certifications. Pass `base_dir` to persist
    each certified manifest as a small JSON record on disk (mirroring ResearchRunStore's
    existing on-disk persistence pattern), so the guarantee holds across process restarts too.
    This never writes the dataset's Parquet bytes themselves — only the small manifest record."""

    def __init__(self, base_dir: Optional[str] = None):
        self._store: Dict[Tuple[str, str], PersistentDatasetManifest] = {}
        self.base_dir = base_dir
        if self.base_dir:
            os.makedirs(self.base_dir, exist_ok=True)

    def _disk_path(self, dataset_id: str, dataset_version: str) -> Optional[Path]:
        if not self.base_dir:
            return None
        safe_id = dataset_id.replace("/", "_")
        safe_version = dataset_version.replace("/", "_")
        return Path(self.base_dir) / f"{safe_id}__{safe_version}.json"

    def _load_from_disk(self, dataset_id: str, dataset_version: str) -> Optional[PersistentDatasetManifest]:
        path = self._disk_path(dataset_id, dataset_version)
        if not path or not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return PersistentDatasetManifest(**data)

    def certify(self, manifest: PersistentDatasetManifest) -> None:
        key = (manifest.dataset_id, manifest.dataset_version)
        existing = self._store.get(key) or self._load_from_disk(manifest.dataset_id, manifest.dataset_version)
        if existing is not None:
            if existing.content_sha256 != manifest.content_sha256:
                raise ValueError(
                    f"FAIL CLOSED: dataset_version '{manifest.dataset_version}' for dataset "
                    f"'{manifest.dataset_id}' is already certified with content_sha256="
                    f"'{existing.content_sha256}', which differs from the newly computed "
                    f"'{manifest.content_sha256}'. A dataset_version identifies immutable "
                    "content; re-certifying different content under the same version is prohibited."
                )
            self._store[key] = existing
            return  # identical re-certification is a harmless no-op
        self._store[key] = manifest
        path = self._disk_path(manifest.dataset_id, manifest.dataset_version)
        if path:
            with open(path, "w") as f:
                f.write(to_canonical_json(asdict(manifest)))

    def get(self, dataset_id: str, dataset_version: str) -> Optional[PersistentDatasetManifest]:
        key = (dataset_id, dataset_version)
        if key in self._store:
            return self._store[key]
        loaded = self._load_from_disk(dataset_id, dataset_version)
        if loaded:
            self._store[key] = loaded
        return loaded
