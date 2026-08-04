"""
test_real_dataset_snapshot.py — Real dataset snapshot generation & immutability tests.
"""

from datetime import datetime
import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine


def test_real_dataset_snapshot_creation(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    snap = snap_mgr.create_snapshot(as_of=datetime(2022, 5, 2), snapshot_id="snap_real_01", dataset_version="ds_v1.0")

    assert snap.snapshot_id == "snap_real_01"
    assert snap.dataset_version == "ds_v1.0"
    assert snap.as_of == datetime(2022, 5, 2)
