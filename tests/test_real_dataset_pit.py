"""
test_real_dataset_pit.py — Point-in-Time temporal semantics audit on real historical datasets.
"""

from datetime import datetime
import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine


def test_real_dataset_pit_enforcement(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    pit_report = engine.run_snapshot_pit_audit(snap_mgr)

    assert pit_report["status"] == "PASSED"
    assert pit_report["pit_violation_count"] == 0
    assert pit_report["snapshot_a_rows"] < pit_report["snapshot_b_rows"]
