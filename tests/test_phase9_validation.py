"""
test_phase9_validation.py
Phase 9 Data Integrity Audit, Market Index Symbol Mapping, Provider Contract, Demo Mode & Cloud Fallback Unit Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.symbol_utils import normalize_ashare_code
from src.data.demo_provider import DemoMarketDataProvider
from src.data.akshare_provider import AkShareProvider
from src.data.cache import LocalCache
from src.services.research_service import ResearchService
from src.system.integrity import ResearchIntegrityChecker


def test_index_symbol_mapping():
    sh_index = normalize_ashare_code("000001.SH")
    assert sh_index["code6"] == "000001"
    assert sh_index["market"] == "SH"
    assert sh_index["prefix"] == "sh000001"

    csi300 = normalize_ashare_code("000300")
    assert csi300["code6"] == "000300"
    assert csi300["market"] == "SH"

    sz_index = normalize_ashare_code("399001")
    assert sz_index["market"] == "SZ"
    assert sz_index["prefix"] == "sz399001"


def test_market_data_integrity():
    p = DemoMarketDataProvider()
    m = p.get_latest("000300.SH")
    assert m.symbol == "000300.SH"
    assert m.close > 0.0


def test_market_data_freshness():
    p = DemoMarketDataProvider()
    m = p.get_latest("600519.SH")
    assert m.timestamp is not None
    assert len(m.timestamp) > 0


def test_provider_contract():
    p = DemoMarketDataProvider()
    h = p.get_history("600519.SH")
    assert not h.empty
    assert "close" in h.columns
    assert "date" in h.columns


def test_demo_mode():
    p = DemoMarketDataProvider()
    df = p.get_history("600519.SH")
    assert len(df) > 500
    m = p.get_latest("000001.SH")
    assert m.close == 3280.50



def test_multi_session_isolation(tmp_path):
    cache1 = LocalCache(cache_dir=str(tmp_path / "c1"))
    cache2 = LocalCache(cache_dir=str(tmp_path / "c2"))

    df = pd.DataFrame([{"date": "2026-08-01", "close": 100.0}])
    cache1.save("600519", df)

    p1 = AkShareProvider(cache=cache1)
    p2 = AkShareProvider(cache=cache2)

    assert not p1.get_history("600519").empty
    assert p2.cache.load("600519") is None or p2.cache.load("600519").empty


def test_cloud_fallback(tmp_path):
    items = ResearchIntegrityChecker.get_integrity_status()
    assert len(items) >= 6
    assert all(x["status"] == "PASSED" for x in items)
