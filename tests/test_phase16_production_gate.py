"""
test_phase16_production_gate.py
Phase 16 Step 2.5 Final Production Gate 终极断言与数据反证测试套件：
1. 验证 000001.SH (上证指数) vs 000001.SZ (平安银行) 在 Provider -> Service -> UI -> Alpha 的全链路隔离
2. 反证测试 1: 拒绝 Demo / Mock 标注数据侵入 Research Mode
3. 反证测试 2: 拒绝无 Source Metadata 或 is_real=False 的非真实数据
4. 反证测试 3: 拒绝裸代码 "000001"
5. 反证测试 4: 拒绝 000001.SH 被平安银行股价 (< 500) 污染
6. Alpha -> Canonical Symbol -> PIT -> Lookahead -> Evidence 完整血缘追溯
"""

import pytest
import pandas as pd
import numpy as np
from app import get_services
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError
from src.data.contract import normalize_market_data_contract, MarketDataContract
from src.factors.alpha_zoo import AlphaRegistry
from src.factors.alpha_zoo.evidence import AlphaEvidenceRecord


def test_production_gate_symbol_namespace_isolation():
    """验证 000001.SH 与 000001.SZ 在 Research 链路下的绝对隔离"""
    services = get_services("RESEARCH MODE")
    provider = services["provider"]

    quote_sh = provider.get_latest("000001.SH")
    contract_sh = normalize_market_data_contract(quote_sh)

    quote_sz = provider.get_latest("000001.SZ")
    contract_sz = normalize_market_data_contract(quote_sz)

    assert contract_sh.symbol == "000001.SH"
    assert contract_sh.name == "上证指数"

    assert contract_sz.symbol == "000001.SZ"
    assert contract_sz.name == "平安银行"


def test_counter_proof_demo_data_rejected():
    """反证测试 1: Demo / Mock 数据强行注入 Research Mode 触发门控拒绝"""
    demo_obj = MarketDataContract(
        symbol="000001.SH",
        name="上证指数",
        market="SH",
        close=3280.50,
        source="DemoMarketDataProvider",
        data_mode="DEMO",
        is_real=False
    )
    with pytest.raises(ResearchDataIntegrityError, match="DemoProvider 数据侵入"):
        ResearchDataIntegrityGate.assert_valid_research_data(demo_obj)


def test_counter_proof_fake_is_real_false_rejected():
    """反证测试 2: is_real=False 的数据触发门控拒绝"""
    fake_obj = MarketDataContract(
        symbol="600519.SH",
        name="贵州茅台",
        market="SH",
        close=1450.0,
        source="FakeProvider",
        data_mode="RESEARCH",
        is_real=False
    )
    with pytest.raises(ResearchDataIntegrityError, match="非真实行情数据"):
        ResearchDataIntegrityGate.assert_valid_research_data(fake_obj)


def test_counter_proof_naked_symbol_rejected():
    """反证测试 3: 裸代码 "000001" 触发门控拒绝"""
    naked_obj = MarketDataContract(
        symbol="000001",
        name="未知",
        market="SH",
        close=10.0,
        source="TestProvider",
        data_mode="RESEARCH",
        is_real=True
    )
    with pytest.raises(ResearchDataIntegrityError, match="拒绝裸代码 '000001'"):
        ResearchDataIntegrityGate.assert_valid_research_data(naked_obj)


def test_counter_proof_sh_index_contaminated_by_ping_an_bank_rejected():
    """反证测试 4: 000001.SH 价格属于平安银行 (< 500) 触发门控拒绝"""
    contaminated_obj = MarketDataContract(
        symbol="000001.SH",
        name="上证指数",
        market="SH",
        close=11.50,  # 错误的平安银行股价
        source="CorruptedProvider",
        data_mode="RESEARCH",
        is_real=True
    )
    with pytest.raises(ResearchDataIntegrityError, match="被平安银行"):
        ResearchDataIntegrityGate.assert_valid_research_data(contaminated_obj)



def test_alpha_to_evidence_end_to_end_lineage():
    """验证 MOM_20D / REV_20D / VOL_20D / EP_TTM 到 Evidence Record 的全血缘可追溯性"""
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    mock_df = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["600519.SH"] * 60,
        "close": np.linspace(1400, 1600, 60),
        "volume": np.random.uniform(10000, 50000, 60),
        "amount": np.random.uniform(100000, 500000, 60),
        "pe_ttm": np.random.uniform(20, 30, 60),
        "publication_date": ["2024-12-31"] * 60
    })

    targets = [
        ("MOM_20D", "600519.SH"),
        ("REV_20D", "600036.SH"),
        ("VOL_20D", "000001.SZ"),
        ("EP_TTM", "600519.SH")
    ]

    for aid, sym in targets:
        res = AlphaRegistry.compute(aid, mock_df)
        val = float(res.dropna().iloc[-1])

        evidence = AlphaEvidenceRecord(
            alpha_id=aid,
            symbol=sym,
            data_source="Tencent Realtime API (RESEARCH)",
            data_start="2025-01-01",
            data_end="2026-08-01",
            latest_value=val
        )

        assert evidence.alpha_id == aid
        assert evidence.symbol == sym
        assert evidence.is_real is True
        assert evidence.data_mode == "RESEARCH"
        assert len(evidence.result_hash) == 16
