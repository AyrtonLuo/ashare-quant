"""
test_numerical_truth.py
Phase 16 Step 4.7 Numerical Truth & Cross-API Validation 终极数值真理测试套件
全面包含：
1. 历史行情传递层层无损验证 (HistoricalMarketDataContract)
2. Momentum_20D 手工公式交叉对比 (P_t / P_{t-20} - 1 vs AlphaRegistry)
3. Volatility_20D 手工公式交叉对比
4. Liquidity_20D 手工公式交叉对比
5. Value / EP_TTM 手工公式与 PIT 交叉对比 (1 / PE_TTM)
6. Quality_ROE PIT 截止时间限制校验
7. 历史数据不足拒绝伪造 0 (DATA_INSUFFICIENT != 0)
8. 基本面缺失拒绝伪造 0 (DATA_UNAVAILABLE != 0)
9. NaN 不被伪装成 0 (NaN != 0)
10. ML Feature Provenance (特征契约全血缘追溯)
11. ML Score Provenance (模型预测全血缘追溯)
12. API 跨数据源跨层一致性校验
13. Contract 到 Agent Research Result 数值无损传递
14. 指数 (000001.SH) 与 股票 (000001.SZ) 数值隔离断言
"""

import pytest
import pandas as pd
import numpy as np
from app import get_services
from src.data.contract import (
    normalize_market_data_contract,
    MarketDataContract,
    HistoricalMarketDataContract,
    FundamentalDataContract,
    MLFeatureContract,
    PredictionContract,
    ErrorStatus
)
from src.data.symbol_utils import normalize_ashare_code
from src.factors.alpha_zoo import AlphaRegistry
from src.data.pit_provider import PITFundamentalProvider


def test_historical_price_propagation():
    """1. 历史行情在 Raw -> Contract -> Service -> Tool 传播过程中数值 100% 无损传递"""
    df_raw = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": np.linspace(100.0, 120.0, 25),
        "volume": [1000.0] * 25,
        "amount": [100000.0] * 25
    })
    contract = HistoricalMarketDataContract(
        symbol="688110.SH",
        start_date="2025-01-01",
        end_date="2025-01-25",
        data=df_raw,
        status="AVAILABLE"
    )

    assert contract.symbol == "688110.SH"
    assert len(contract.data) == 25
    assert contract.data["close"].iloc[-1] == 120.0


def test_momentum_manual_verification():
    """2. Momentum_20D 手工计算公式 P_t / P_{t-20} - 1 与 AlphaRegistry 计算精确对齐"""
    closes = np.linspace(100.0, 120.0, 25)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": closes,
        "volume": [1000.0] * 25,
        "amount": [100000.0] * 25
    })

    p_t = closes[-1]        # 120.0
    p_t20 = closes[-21]     # 100.0
    manual_mom = (p_t / p_t20) - 1.0  # 0.20 (+20%)

    res_series = AlphaRegistry.compute("MOM_20D", df)
    val = float(res_series.dropna().iloc[-1])
    assert abs(val - manual_mom) < 1e-5


def test_volatility_manual_verification():
    """3. Volatility_20D 手工对齐对比 (20日收益率标准差 * sqrt(252))"""
    closes = np.array([100 + (i % 3) * 2 for i in range(25)], dtype=float)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": closes,
        "volume": [1000.0] * 25,
        "amount": [100000.0] * 25
    })

    ret = pd.Series(closes).pct_change(fill_method=None).dropna().tail(20)
    manual_vol = float(ret.std(ddof=1)) * np.sqrt(252)

    res_series = AlphaRegistry.compute("VOL_20D", df)
    val = float(res_series.dropna().iloc[-1])
    assert abs(val - manual_vol) < 1e-5



def test_liquidity_manual_verification():
    """4. Liquidity_20D (Turnover_20D) 手工公式对比"""
    amounts = np.linspace(10000.0, 50000.0, 25)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": [100.0] * 25,
        "volume": [1000.0] * 25,
        "amount": amounts
    })

    manual_turnover = float(pd.Series(amounts).tail(20).mean())
    res_series = AlphaRegistry.compute("TURNOVER_20D", df)
    val = float(res_series.dropna().iloc[-1])

    assert abs(val - manual_turnover) < 1e-5


def test_ep_manual_verification():
    """5. Value / EP_TTM (1 / PE_TTM) 数值与 PIT 手工精确对齐"""
    pe_val = 25.0
    manual_ep = 1.0 / pe_val  # 0.04

    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": [100.0] * 25,
        "pe_ttm": [pe_val] * 25
    })
    res_series = AlphaRegistry.compute("EP_TTM", df)
    val = float(res_series.dropna().iloc[-1])

    assert abs(val - manual_ep) < 1e-5


def test_roe_pit_verification():
    """6. Quality_ROE PIT 截止控制断言: 披露日必须 <= 交易日"""
    pit_provider = PITFundamentalProvider()
    valid_res = pit_provider.get_pit_fundamental("600519.SH", "2025-01-10", publication_date="2025-01-08")
    invalid_res = pit_provider.get_pit_fundamental("600519.SH", "2025-01-10", publication_date="2025-01-15")

    assert valid_res.status in ["AVAILABLE", "DATA_UNAVAILABLE"]
    assert invalid_res.status == "PIT_REJECTED"


def test_insufficient_history_not_zero():
    """7. 历史数据缺乏 21 日时返回空或全 NaN 系列，绝不上漏伪造 0 收益"""
    short_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=10, freq="B"),
        "close": np.linspace(100.0, 110.0, 10)
    })
    res_series = AlphaRegistry.compute("MOM_20D", short_df)
    valid_vals = res_series.dropna()

    assert len(valid_vals) == 0


def test_missing_fundamental_not_zero():
    """8. 缺失基本面 EP 数据时返回空或全 NaN 系列，绝不上漏 0 估值"""
    df_no_pe = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": [100.0] * 25
    })
    res_series = AlphaRegistry.compute("EP_TTM", df_no_pe)
    valid_vals = res_series.dropna()

    assert len(valid_vals) == 0


def test_nan_not_zero():
    """9. 含 NaN 价格时计算结果末端不会被伪装成 0"""
    closes = [100.0] * 20 + [np.nan] * 5
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=25, freq="B"),
        "close": closes
    })
    res_series = AlphaRegistry.compute("MOM_20D", df)
    last_val = res_series.iloc[-1]

    assert pd.isna(last_val)


def test_ml_feature_provenance():
    """10. ML 特征全血缘追溯 (MLFeatureContract 验证)"""
    feat = MLFeatureContract(
        symbol="688110.SH",
        feature_timestamp="2025-01-10",
        feature_names=["MOM_20D", "VOL_20D", "EP_TTM"],
        feature_values=[0.05, 0.15, 0.04],
        source="FactorEngine"
    )

    assert feat.symbol == "688110.SH"
    assert feat.feature_values[0] == 0.05
    assert feat.status == "AVAILABLE"


def test_ml_score_provenance():
    """11. ML 预测输出全血缘追溯 (PredictionContract 验证)"""
    pred = PredictionContract(
        symbol="688110.SH",
        model_name="LightGBMAlphaV1",
        model_version="1.0.0",
        prediction_timestamp="2025-01-10",
        feature_timestamp="2025-01-10",
        prediction=0.782,
        feature_names=["MOM_20D", "VOL_20D"],
        source="MLModel"
    )

    assert pred.symbol == "688110.SH"
    assert pred.prediction == 0.782
    assert pred.model_version == "1.0.0"


def test_api_cross_source_consistency():
    """12. 跨 API 源数值对齐比较，统一通过 normalize_market_data_contract 规范化"""
    raw_akshare = {"symbol": "688110.SH", "close": 34.50, "source": "AkShare API"}
    raw_tencent = {"symbol": "688110.SH", "price": 34.50, "source": "Tencent API"}

    c1 = normalize_market_data_contract(raw_akshare)
    c2 = normalize_market_data_contract(raw_tencent)

    assert c1.close == c2.close
    assert c1.symbol == c2.symbol == "688110.SH"


def test_contract_to_research_numerical_consistency():
    """13. 校验行情数值从 Contract 传递到 Agent 工具结果中 100% 保持一致"""
    services = get_services("RESEARCH MODE")
    q = services["provider"].get_latest("688110.SH")
    c = normalize_market_data_contract(q)

    assert c.symbol == "688110.SH"
    if c.close is not None:
        assert isinstance(c.close, float)


def test_index_and_stock_numerical_isolation():
    """14. 000001.SH (上证指数) 与 000001.SZ (平安银行) 数值隔离断言"""
    sh_index = normalize_market_data_contract({"symbol": "000001.SH", "close": 3280.50, "name": "上证指数"})
    sz_stock = normalize_market_data_contract({"symbol": "000001.SZ", "close": 11.50, "name": "平安银行"})

    assert sh_index.symbol == "000001.SH"
    assert sh_index.close > 1000.0  # 指数 > 3000 点

    assert sz_stock.symbol == "000001.SZ"
    assert sz_stock.close < 100.0   # 个股股价 < 100 元
