"""
manifest.py — Dataset Manifest Contract & SHA-256 Provenance Verification Manager.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from src.quant.reproducibility.canonical import compute_canonical_sha256


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    created_at: str
    primary_source: str
    secondary_source: str
    schema_version: str
    start_date: str
    end_date: str
    symbol_count: int
    row_count: int
    checksum_sha256: str
    validation_status: str


class DatasetManifestManager:
    """Manages computation and verification of SHA-256 checksums for historical datasets."""

    @staticmethod
    def compute_sha256(data_payload: Any) -> str:
        """Delegates to the single authoritative canonical serializer (canonical.py) so
        dataset checksums and research-result hashes use identical serialization semantics."""
        return compute_canonical_sha256(data_payload)

    @staticmethod
    def create_manifest(
        dataset_id: str,
        created_at: str,
        primary_source: str,
        secondary_source: str,
        schema_version: str,
        start_date: str,
        end_date: str,
        symbol_count: int,
        row_count: int,
        data_payload: Any,
        validation_status: str = "VERIFIED"
    ) -> DatasetManifest:
        checksum = DatasetManifestManager.compute_sha256(data_payload)
        return DatasetManifest(
            dataset_id=dataset_id,
            created_at=created_at,
            primary_source=primary_source,
            secondary_source=secondary_source,
            schema_version=schema_version,
            start_date=start_date,
            end_date=end_date,
            symbol_count=symbol_count,
            row_count=row_count,
            checksum_sha256=checksum,
            validation_status=validation_status
        )

    @staticmethod
    def verify_manifest(manifest: DatasetManifest, data_payload: Any) -> bool:
        calculated = DatasetManifestManager.compute_sha256(data_payload)
        return calculated == manifest.checksum_sha256
