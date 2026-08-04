"""
test_real_dataset_quality.py — Real historical dataset quality audit tests.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine, VERIFICATION_SYMBOLS


def test_real_dataset_quality_audit(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    report = engine.run_quality_audit(manifest, store)

    assert report["dataset_id"] == "real_historical_dataset_v1"
    assert report["symbol_count"] == 20
    assert report["null_critical_fields"] == 0
    assert report["duplicate_rows"] == 0
    assert report["quality_status"] == "PASSED_CLEAN"
