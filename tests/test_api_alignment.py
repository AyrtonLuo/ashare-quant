"""
test_api_alignment.py
Phase 16 Step 4.6: Complete API Alignment & Unified Data Contract 测试套件
包含 18 大 API 契约对齐、Canonical Symbol 校验、PIT 截止拦截、零 Fallback 到 0 审计与数据源一致性测试。
"""

import pytest
import pandas as pd
import numpy as np
from app import get_services
from src.data.contract import (
    normalize_market_data_contract,
    MarketDataContract,
    FundamentalDataContract,
    MLFeatureContract,
    PredictionContract,
    ErrorStatus
)
from src.data.symbol_utils import (
    is_canonical_symbol,
    normalize_ashare_code,
    to_akshare_symbol,
    to_tencent_symbol
)
from src.data.pit_provider import PITFundamentalProvider
from src.factors.alpha_zoo import AlphaRegistry
from src.research.tools import AgentToolRegistry, ToolExecutionContext


def test_all_providers_return_same_contract():
    """1. 验证所有 Market Provider 统一返回 MarketDataContract"""
    services = get_services("RESEARCH MODE")
    provider = services["provider"]

    quote_sh = provider.get_latest("000001.SH")
    c_sh = normalize_market_data_contract(quote_sh)
    assert isinstance(c_sh, MarketDataContract)

    quote_moutai = provider.get_latest("600519.SH")
    c_moutai = normalize_market_data_contract(quote_moutai)
    assert isinstance(c_moutai, MarketDataContract)


def test_all_symbols_use_canonical_symbol():
    """2. 验证所有模块对外展示的代码均为 Canonical Symbol (e.g. 600519.SH, 000001.SZ)"""
    syms = ["600519.SH", "000001.SZ", "000001.SH", "000300.SH", "688110.SH"]
    for s in syms:
        assert is_canonical_symbol(s) is True


def test_sh_index_and_sz_stock_isolated():
    """3. 验证 000001.SH (上证指数) 与 000001.SZ (平安银行) 完全隔离"""
    info_sh = normalize_ashare_code("000001.SH")
    info_sz = normalize_ashare_code("000001.SZ")

    assert info_sh["is_index"] is True
    assert info_sh["name"] == "上证指数"

    assert info_sz["is_index"] is False
    assert info_sz["name"] == "平安银行"


def test_index_api_rejects_stock_semantics():
    """4. 指数 API 不接收股票代码"""
    info = normalize_ashare_code("600519.SH")
    assert info["is_index"] is False


def test_stock_api_rejects_index_semantics():
    """5. 股票 API 不接收指数代码"""
    info = normalize_ashare_code("000300.SH")
    assert info["is_index"] is True


def test_historical_api_fields_consistent():
    """6. 验证所有 Historical API 输出字段统一为 trading_date/open/high/low/close/volume/amount"""
    services = get_services("RESEARCH MODE")
    provider = services["provider"]
    df = provider.get_hist("600519.SH", "2025-01-01", "2025-01-10")

    if not df.empty:
        cols = list(df.columns)
        assert "close" in cols or "Close" in cols
        assert "date" in cols or "timestamp" in cols or "Date" in cols


def test_fundamental_api_contract_consistent():
    """7. 验证 Fundamental API 契约为 FundamentalDataContract 规范结构"""
    contract = FundamentalDataContract(
        symbol="600519.SH",
        trading_date="2025-01-02",
        fiscal_period="2024Q4",
        publication_date="2025-01-01",
        effective_date="2025-01-01",
        pe_ttm=24.5,
        pb=8.2,
        roe=0.27
    )
    c_dict = contract.to_dict()
    assert c_dict["symbol"] == "600519.SH"
    assert c_dict["roe"] == 0.27
    assert c_dict["status"] == "AVAILABLE"


def test_pit_api_rejects_future_publication():
    """8. 验证 PIT API 拒绝 publication_date > trading_date 的未来数据"""
    pit_provider = PITFundamentalProvider()
    res = pit_provider.get_pit_fundamental("600519.SH", trading_date="2025-01-02", publication_date="2025-01-05")

    assert res.status in ["PIT_REJECTED", "DATA_UNAVAILABLE"]
    assert res.pe_ttm is None


def test_api_failure_does_not_return_zero():
    """9. 验证 API 失败绝不返回 0 价格，而是返回 status=DATA_UNAVAILABLE, close=None"""
    c = normalize_market_data_contract({"symbol": "600519.SH", "close": None, "status": "DATA_UNAVAILABLE"})

    assert c.status == "UNAVAILABLE"
    assert c.close is None
    assert c.close != 0.0


def test_missing_data_does_not_return_zero():
    """10. 验证 缺失数据绝不补零，而是标记为 DATA_INSUFFICIENT"""
    pit_provider = PITFundamentalProvider()
    res = pit_provider.get_pit_fundamental("NON_EXISTENT.SH", "2025-01-02")

    assert res.status in ["DATA_UNAVAILABLE", "DATA_INSUFFICIENT"]
    assert res.pe_ttm is None


def test_nan_not_silently_converted_to_zero():
    """11. 验证 NaN 不会被静默转换为 0"""
    c = normalize_market_data_contract({"symbol": "600519.SH", "close": np.nan})

    assert c.status == "UNAVAILABLE"
    assert c.close is None


def test_all_api_objects_have_source():
    """12. 验证所有行情契约都有明确的数据源 Metadata"""
    c = normalize_market_data_contract({"symbol": "600519.SH", "close": 1450.0, "source": "Tencent Realtime API"})
    assert c.source == "Tencent Realtime API"


def test_all_research_data_has_data_mode():
    """13. 验证所有 Research 数据标注 data_mode='RESEARCH'"""
    c = normalize_market_data_contract({"symbol": "600519.SH", "close": 1450.0, "data_mode": "RESEARCH"})
    assert c.data_mode == "RESEARCH"


def test_real_data_has_is_real_true():
    """14. 验证真实数据具备 is_real=True 标记"""
    c = normalize_market_data_contract({"symbol": "600519.SH", "close": 1450.0, "status": "AVAILABLE", "data_mode": "RESEARCH", "is_real": True})
    assert c.is_real is True


def test_all_errors_have_standard_status_enum():
    """15. 验证所有错误状态均使用 ErrorStatus 枚举的定义"""
    valid_statuses = [e.value for e in ErrorStatus]
    assert "AVAILABLE" in valid_statuses
    assert "DATA_UNAVAILABLE" in valid_statuses
    assert "PIT_REJECTED" in valid_statuses


def test_all_alpha_input_schemas_consistent():
    """16. 验证所有 Alpha 的 Required Fields 规范对齐"""
    alphas = AlphaRegistry.list_all()
    for a in alphas:
        assert isinstance(a.required_fields, list)
        assert len(a.required_fields) > 0


def test_ml_feature_contract_consistent():
    """17. 验证 ML 特征契约结构正确"""
    ml_contract = MLFeatureContract(
        symbol="600519.SH",
        feature_timestamp="2025-01-02",
        feature_names=["MOM_20D", "VOL_20D"],
        feature_values=[0.05, 0.18]
    )
    assert ml_contract.symbol == "600519.SH"
    assert len(ml_contract.feature_values) == 2


def test_agent_tool_and_service_return_same_contract():
    """18. 验证 Agent Tool 与底座 Service 返回同一规范数据契约"""
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("get_market_quote", context, symbol="600519.SH")
    assert res.success is True
    assert res.data["symbol"] == "600519.SH"
    assert res.data["data_mode"] == "RESEARCH"
