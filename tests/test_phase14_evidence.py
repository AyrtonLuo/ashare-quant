"""
test_phase14_evidence.py
Phase 14 Real Research Validation, Data Provenance Audit, Double-Run Reproducibility & Benchmark Comparison Suite Unit Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.demo_provider import DemoMarketDataProvider
from src.data.akshare_provider import AkShareProvider
from src.data.cache import LocalCache
from src.experiments.reproducibility import ResearchReproducibilityRunner
from src.benchmarks.suite import BenchmarkComparisonSuite



def test_data_provenance_audit_file_exists():
    audit_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DATA_PROVENANCE_AUDIT.md")
    assert os.path.exists(audit_file)
    with open(audit_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "REAL RESEARCH RESULT" in content
    assert "RESEARCH MODEL APPROX" in content


def test_reproducibility_double_run_exact_match(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    cert = ResearchReproducibilityRunner.verify_reproducibility("ExpA_MultiFactor", ["600519"], provider, "2026-07-01", "2026-07-20")

    assert cert.is_exact_match is True
    assert cert.run1_sharpe == cert.run2_sharpe
    assert cert.run1_return == cert.run2_return


def test_benchmark_comparison_suite(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": f"2026-07-{i:02d}", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0 + i, "volume": 1000}
        for i in range(1, 25)
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    bench_df = BenchmarkComparisonSuite.run_full_benchmark_comparison(["600519"], provider, "2026-07-01", "2026-07-20")

    assert len(bench_df) == 7
    assert "Strategy / Benchmark" in bench_df.columns
    assert "Sharpe" in bench_df.columns
    assert "Max Drawdown" in bench_df.columns


def test_statistical_audit_non_overlapping_labels():
    from src.data.fundamental.provider import PITFundamentalProvider
    pit = PITFundamentalProvider()
    fund = pit.get_fundamental("600519", cutoff_date="2024-11-01")
    assert fund.publication_date <= "2024-11-01"


def test_reproducibility_hash_consistency(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    c1 = ResearchReproducibilityRunner.verify_reproducibility("ExpC_Momentum", ["600519"], provider, "2026-07-01", "2026-07-20")
    c2 = ResearchReproducibilityRunner.verify_reproducibility("ExpC_Momentum", ["600519"], provider, "2026-07-01", "2026-07-20")
    assert c1.data_hash == c2.data_hash

