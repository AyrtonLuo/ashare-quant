"""
test_phase15_contract.py
Phase 15 MarketDataContract & End-to-End Lineage Integration Tests
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.contract import MarketDataContract, normalize_market_data_contract
from src.data.models import MarketData
from src.data.symbol_utils import normalize_ashare_code, INDEX_SYMBOLS, STOCK_SYMBOLS
from src.data.akshare_provider import AkShareProvider
from src.data.demo_provider import DemoMarketDataProvider
from src.services.research_service import ResearchService
from app import get_services, render_market


def test_market_data_contract():
    # 测试 Dict 规范化
    raw_dict = {"symbol": "000001.SH", "price": 3285.5, "status": "AVAILABLE"}
    contract1 = normalize_market_data_contract(raw_dict)
    assert contract1.symbol == "000001.SH"
    assert contract1.close == 3285.5
    assert contract1.market == "SH"
    assert contract1.status == "AVAILABLE"
    assert contract1.is_real is True

    # 测试旧版本解包无 status 字段的对象
    old_md = MarketData(symbol="600519.SH", timestamp="2026-08-01", open=1400.0, high=1450.0, low=1390.0, close=1420.0)
    delattr(old_md, "status")  # 模拟反序列化丢失 status 属性
    contract2 = normalize_market_data_contract(old_md)
    assert hasattr(contract2, "status")
    assert contract2.status == "AVAILABLE"
    assert contract2.close == 1420.0


def test_index_symbol_disambiguation():
    sh_info = normalize_ashare_code("000001.SH")
    sz_info = normalize_ashare_code("000001.SZ")

    assert sh_info["suffix"] == "000001.SH"
    assert sh_info["is_index"] is True
    assert sh_info["name"] == "上证指数"

    assert sz_info["suffix"] == "000001.SZ"
    assert sz_info["is_index"] is False
    assert sz_info["name"] == "平安银行"


def test_research_mode_real_data_only(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": 3300.0, "status": "AVAILABLE", "source": "Tencent Realtime API"})
    services = get_services("RESEARCH MODE")
    provider = services["provider"]
    quote = provider.get_latest("000001.SH")
    contract = normalize_market_data_contract(quote)

    assert contract.is_real is True
    assert contract.data_mode == "RESEARCH"
    assert contract.symbol == "000001.SH"
    assert contract.close == 3300.0


def test_research_mode_api_failure_returns_unavailable(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    provider = AkShareProvider(use_cache=False)
    raw = provider.get_latest("000001.SH")
    contract = normalize_market_data_contract(raw)

    assert contract.status == "UNAVAILABLE"
    assert contract.close is None
    assert contract.is_real is False


def test_research_mode_never_uses_demo_data():
    services = get_services("RESEARCH MODE")
    provider = services["provider"]
    assert not isinstance(provider, DemoMarketDataProvider)


def test_research_mode_never_uses_hardcoded_price(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    provider = AkShareProvider(use_cache=False)
    contract = normalize_market_data_contract(provider.get_latest("000001.SH"))

    assert contract.close != 3280.50
    assert contract.close != 3832.26
    assert contract.close != 11.50
    assert contract.close != 10.00
    assert contract.close is None


def test_demo_mode_uses_demo_provider():
    services = get_services("DEMO MODE")
    provider = services["provider"]
    assert isinstance(provider, DemoMarketDataProvider)
    contract = normalize_market_data_contract(provider.get_latest("000001.SH"))
    assert contract.data_mode == "DEMO"
    assert contract.is_real is False


def test_shanghai_index_symbol_is_000001_SH():
    info = normalize_ashare_code("000001.SH")
    assert info["code6"] == "000001"
    assert info["market"] == "SH"
    assert info["suffix"] == "000001.SH"


def test_ping_market_data_contract():
    info = normalize_ashare_code("000001.SZ")
    assert info["code6"] == "000001"
    assert info["market"] == "SZ"
    assert info["suffix"] == "000001.SZ"


def test_render_market_with_unavailable_data(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    services = get_services("RESEARCH MODE")

    # 执行 render_market 无 AttributeError 抛出
    try:
        render_market(services)
        success = True
    except AttributeError:
        success = False

    assert success is True


def test_provider_to_service_to_ui_end_to_end_integration(monkeypatch):
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"name": "贵州茅台", "price": 1450.0, "status": "AVAILABLE", "source": "AkShare Spot API"})
    services = get_services("RESEARCH MODE")
    provider = services["provider"]

    raw = provider.get_latest("600519.SH")
    contract = normalize_market_data_contract(raw)

    assert contract.symbol == "600519.SH"
    assert contract.name == "贵州茅台"
    assert contract.market == "SH"
    assert contract.close == 1450.0
    assert contract.status == "AVAILABLE"
    assert contract.source == "AkShare Spot API"
    assert contract.is_real is True

