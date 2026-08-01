"""
test_phase15_integrity.py
Phase 15 Real Market Data Integrity Refactor & Lineage Gate Unit Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.symbol_utils import normalize_ashare_code, INDEX_SYMBOLS, STOCK_SYMBOLS
from src.data.akshare_provider import AkShareProvider
from src.data.demo_provider import DemoMarketDataProvider
from src.data.cache import LocalCache
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError


def test_research_mode_never_uses_demo_provider():
    from app import get_services
    services = get_services("RESEARCH MODE")
    provider = services["provider"]
    assert not isinstance(provider, DemoMarketDataProvider)
    assert isinstance(provider, AkShareProvider)


def test_research_mode_never_uses_hardcoded_price(monkeypatch):
    # 模拟 API 抛异常
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    cache = LocalCache()
    provider = AkShareProvider(cache=cache, use_cache=False)

    m = provider.get_latest("000001.SH")
    assert m.close is None
    assert m.status == "DATA_UNAVAILABLE"
    assert m.is_real is False


def test_research_mode_api_failure_returns_unavailable(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    provider = AkShareProvider(use_cache=False)
    quote = provider.get_latest("600519.SH")

    assert quote.status == "DATA_UNAVAILABLE"
    assert quote.close is None
    assert quote.source is None


def test_000001_SH_maps_to_sse_index():
    info = normalize_ashare_code("000001.SH")
    assert info["suffix"] == "000001.SH"
    assert info["is_index"] is True
    assert info["name"] == "上证指数"


def test_000001_SZ_maps_to_ping_an_bank():
    info = normalize_ashare_code("000001.SZ")
    assert info["suffix"] == "000001.SZ"
    assert info["is_index"] is False
    assert info["name"] == "平安银行"


def test_index_and_stock_symbol_namespace_isolated():
    assert INDEX_SYMBOLS["SSE_COMPOSITE"] == "000001.SH"
    assert STOCK_SYMBOLS["PING_AN_BANK"] == "000001.SZ"
    assert INDEX_SYMBOLS["SSE_COMPOSITE"] != STOCK_SYMBOLS["PING_AN_BANK"]


def test_market_quote_contains_source(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=False)
    quote = provider.get_latest("600519.SH")
    assert hasattr(quote, "source")


def test_market_quote_contains_timestamp(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=False)
    quote = provider.get_latest("600519.SH")
    assert hasattr(quote, "timestamp")


def test_market_quote_contains_symbol(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    provider = AkShareProvider(cache=cache, use_cache=False)
    quote = provider.get_latest("600519.SH")
    assert quote.symbol == "600519.SH"


def test_real_quote_has_is_real_true(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": 1450.0, "status": "AVAILABLE", "source": "AkShare Test"})
    provider = AkShareProvider(use_cache=False)
    quote = provider.get_latest("600519.SH")
    assert quote.is_real is True
    assert quote.status == "AVAILABLE"
    assert quote.close == 1450.0


def test_unavailable_quote_has_no_price(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    provider = AkShareProvider(use_cache=False)
    quote = provider.get_latest("000001.SH")
    assert quote.close is None
    assert quote.open is None
    assert quote.high is None
    assert quote.low is None


def test_demo_mode_only_uses_demo_provider():
    from app import get_services
    services = get_services("DEMO MODE")
    provider = services["provider"]
    assert isinstance(provider, DemoMarketDataProvider)
    quote = provider.get_latest("000001.SH")
    assert quote.data_mode == "DEMO"
    assert quote.is_real is False


def test_ambiguous_legacy_parquet_is_rejected(tmp_path):
    cache = LocalCache(cache_dir=str(tmp_path))
    ambiguous_path = os.path.join(str(tmp_path), "000001.parquet")
    df = pd.DataFrame([{"date": "2026-07-31", "close": 11.63}])
    df.to_parquet(ambiguous_path)

    res = cache.load("000001.SH")
    assert res is None


def test_ui_contains_no_hardcoded_market_price():
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert '"3,280.50"' not in content
    assert '"10,450.20"' not in content
    assert '"2,180.10"' not in content


def test_research_quote_close_not_3280_50(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    provider = AkShareProvider(use_cache=False)
    quote = provider.get_latest("000001.SH")
    assert quote.close != 3280.50
    assert quote.close != 3832.26
    assert quote.close != 11.50
    assert quote.close != 10.00
    assert quote.close is None



def test_integrity_gate_raises_on_unavailable():
    provider = AkShareProvider(use_cache=False)
    fake_unavailable_quote = provider.get_latest("000001.SH")
    fake_unavailable_quote.status = "DATA_UNAVAILABLE"
    fake_unavailable_quote.is_real = False

    with pytest.raises(ResearchDataIntegrityError):
        ResearchDataIntegrityGate.assert_valid_research_data(fake_unavailable_quote, context="Backtest Engine")
