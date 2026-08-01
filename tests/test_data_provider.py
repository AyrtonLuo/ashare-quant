"""
test_data_provider.py
Data Layer 2.0 单元测试 (Provider, Models, LocalCache)
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.models import MarketData

from src.data.cache import LocalCache
from src.data.akshare_provider import AkShareProvider


def test_market_data_model():
    md = MarketData(
        symbol="600519",
        timestamp="2026-08-01 10:00:00",
        open=1800.0,
        high=1850.0,
        low=1790.0,
        close=1820.0,
        volume=50000.0,
        amount=91000000.0,
        change_pct=1.11,
        name="贵州茅台"
    )
    d = md.to_dict()
    assert d["symbol"] == "600519"
    assert d["close"] == 1820.0
    assert d["name"] == "贵州茅台"


def test_local_cache_hit_and_miss(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    assert not cache.exists("600519")
    assert cache.load("600519") is None

    test_df = pd.DataFrame([
        {"date": "2026-07-30", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000}
    ])
    cache.save("600519", test_df)
    assert cache.exists("600519")

    loaded = cache.load("600519")
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded.iloc[0]["close"] == 10.2


def test_provider_normalization(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    test_df = pd.DataFrame([
        {"date": "2026-07-30", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000}
    ])
    cache.save("600519", test_df)

    provider = AkShareProvider(cache=cache, use_cache=True)
    df = provider.get_history("600519")
    assert not df.empty
    assert df.iloc[0]["close"] == 10.2


def test_invalid_symbol(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=True)
    md = provider.get_latest("99999999")
    assert md is not None
    assert md.symbol == "99999999"
