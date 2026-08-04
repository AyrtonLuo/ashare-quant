"""
test_persistent_dataset_certification.py — Phase 7I adversarial tests (Directive 007I, Section 9).

Proves dataset identity binds to REAL on-disk Parquet artifacts, not in-memory Python
structures: reload-and-recompute identity, content-change detection, tamper/corruption
detection, missing-artifact fail-closed, replay reproducibility, and version-string reuse
rejection.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data.contracts.market_data import MarketDataContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.domain.persistent_manifest import (
    PersistentDatasetManifestManager,
    PersistentDatasetManifestStore,
)
from src.quant.reproducibility.persistent_dataset_lock import PersistentDatasetLock


def _make_contracts(prices):
    return [
        MarketDataContract(
            symbol="600519.SH", timestamp=datetime(2026, 8, 1 + i), trading_date=f"2026-08-{1 + i:02d}",
            open_price=p, high_price=p + 1, low_price=p - 1, close_price=p, volume=1000.0, amount=100000.0,
            adj_factor=1.0, unadjusted_close=p, trading_status="NORMAL", quality_status="VALID",
            data_origin="GOLDEN_DATASET",
        )
        for i, p in enumerate(prices)
    ]


def _certify(tmp_path, dataset_id, dataset_version, prices, store):
    adapter = ParquetStorageAdapter(base_dir=str(tmp_path))
    adapter.save_market_data(dataset_id, _make_contracts(prices))
    directory = tmp_path / dataset_id
    manifest = PersistentDatasetManifestManager.build_manifest(
        dataset_id, dataset_version, directory, created_at="2026-08-01T00:00:00"
    )
    store.certify(manifest)
    return directory, manifest


# --- TEST 1: create, compute manifest, reload from disk, recompute identity — matches -------

def test_reload_and_recompute_identity_matches(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    assert PersistentDatasetManifestManager.verify(manifest) is True
    assert manifest.row_count == 3
    assert manifest.artifact_type == "PARQUET"
    assert Path(manifest.artifact_path).exists()


# --- TEST 2: modify one dataset value, recompute hash, hash MUST change ---------------------

def test_content_modification_changes_hash(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    file_path = directory / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 999.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    recomputed = PersistentDatasetManifestManager.build_manifest(
        "ds_golden_demo", "v1", directory, created_at=manifest.created_at
    )
    assert recomputed.content_sha256 != manifest.content_sha256


# --- TEST 3: replace a certified artifact while retaining the original identity — FAIL CLOSED

def test_replacing_artifact_content_under_same_version_fails_closed(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    # Tamper with the artifact after certification (simulates a silent replacement).
    file_path = directory / "600519_SH.parquet"
    df = pd.read_parquet(file_path)
    df.loc[0, "close_price"] = 12345.0
    df.to_parquet(file_path, index=False, engine="pyarrow")

    with pytest.raises(ValueError, match="FAIL CLOSED"):
        PersistentDatasetLock.lock("ds_golden_demo", "v1", directory, store)


# --- TEST 4: delete the underlying artifact, attempt replay — FAIL CLOSED -------------------

def test_deleted_artifact_fails_closed_on_lock(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    for f in directory.glob("*.parquet"):
        f.unlink()

    with pytest.raises(FileNotFoundError, match="FAIL CLOSED"):
        PersistentDatasetLock.lock("ds_golden_demo", "v1", directory, store)


# --- TEST 5: corrupt the artifact, attempt replay — FAIL CLOSED -----------------------------

def test_corrupted_artifact_fails_closed_on_lock(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    file_path = directory / "600519_SH.parquet"
    with open(file_path, "wb") as f:
        f.write(b"NOT A VALID PARQUET FILE - CORRUPTED BYTES")

    with pytest.raises(ValueError, match="FAIL CLOSED"):
        PersistentDatasetLock.lock("ds_golden_demo", "v1", directory, store)


# --- TEST 6: same persistent dataset + same everything -> identical result hash -------------

def test_lock_is_deterministic_across_repeated_calls(tmp_path):
    store = PersistentDatasetManifestStore()
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    locked_1 = PersistentDatasetLock.lock("ds_golden_demo", "v1", directory, store)
    locked_2 = PersistentDatasetLock.lock("ds_golden_demo", "v1", directory, store)

    assert locked_1.content_sha256 == locked_2.content_sha256
    assert locked_1.row_count == locked_2.row_count == 3


# --- TEST 7: different content, same dataset_version string — MUST NOT be accepted ----------

def test_different_content_same_version_string_is_rejected(tmp_path):
    store = PersistentDatasetManifestStore()
    _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)

    # A second, genuinely different dataset attempts to certify under the SAME dataset_version.
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        _certify(tmp_path, "ds_golden_demo", "v1", [500.0, 501.0, 502.0], store)

    # Re-certifying the exact same content under the same version is a harmless no-op.
    directory, manifest = _certify(tmp_path, "ds_golden_demo", "v1", [100.0, 101.0, 102.0], store)
    assert store.get("ds_golden_demo", "v1").content_sha256 == manifest.content_sha256


# --- Additional: uncertified dataset can never be locked (no silent trust of raw files) -----

def test_uncertified_dataset_cannot_be_locked(tmp_path):
    store = PersistentDatasetManifestStore()
    adapter = ParquetStorageAdapter(base_dir=str(tmp_path))
    adapter.save_market_data("ds_never_certified", _make_contracts([100.0, 101.0]))
    directory = tmp_path / "ds_never_certified"

    with pytest.raises(ValueError, match="FAIL CLOSED"):
        PersistentDatasetLock.lock("ds_never_certified", "v1", directory, store)


# --- Additional: empty directory cannot be certified (no fabricated empty dataset) ----------

def test_empty_directory_cannot_be_certified(tmp_path):
    empty_dir = tmp_path / "ds_empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="FAIL CLOSED"):
        PersistentDatasetManifestManager.build_manifest("ds_empty", "v1", empty_dir, "2026-08-01T00:00:00")
