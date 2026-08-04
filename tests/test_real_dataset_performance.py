"""
test_real_dataset_performance.py — Parquet & DuckDB storage engine query performance tests.
"""

import pytest
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine


def test_real_dataset_query_performance(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()
    perf_report = engine.run_performance_audit(store)

    assert perf_report["status"] == "PASSED"
    assert perf_report["single_symbol_query_sec"] >= 0.0
    assert perf_report["multi_symbol_query_sec"] >= 0.0
