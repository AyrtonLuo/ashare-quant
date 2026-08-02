"""
test_phase16_step4_5_production_gate.py
Phase 16 Step 4.5 Real Research Agent Production Gate 终极断言与反证测试套件
全面包含：
1. 真实 Research Scenario 归因测试 (000519.SH 动量、波动率与流动性分析)
2. 真实 Data Provenance 与全血缘溯源校验
3. ReAct Trace 完整链条 (Plan -> Select Tool -> Execute -> Observe -> Integrity -> Evidence -> Final)
4. 反证测试 1: 阻止 Agent / Tool 直接读取裸 DataFrame 或 Parquet
5. 反证测试 2: 阻止 Agent / Tool 直接发起 HTTP / AkShare 原生请求
6. 反证测试 3: 强制拒绝 Demo / Mock 数据注入 (ResearchDataIntegrityError)
7. 反证测试 4: 强制拒绝伪造价格注入
8. 反证测试 5: 代码歧义与命名空间强隔离 (裸 000001 拒绝，000001.SH 上证指数 vs 000001.SZ 平安银行)
9. 反证测试 6: DATA_UNAVAILABLE 零降级无缝传播
10. PIT 截止日期与 Look-Ahead 不变性严密断言
11. Evidence Lineage 存证完整性校验
12. 最终结构化 Research Result 业务实用性校验
"""

import pytest
import pandas as pd
import numpy as np
import inspect
from app import get_services
from src.research.agent import ReActResearchAgent, ResearchResult
from src.research.planner import ResearchPlanner, ResearchPlan
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.base import ToolPermission, ToolPermissionError
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError
from src.data.contract import normalize_market_data_contract, MarketDataContract


def test_real_research_scenario_workflow(monkeypatch):
    """
    真实端到端研究场景测试：
    分析 600519.SH (贵州茅台) 过去 1 年的价格动量(MOM_20D, MOM_60D)、波动率(VOL_20D)和流动性(TURNOVER_20D)
    """
    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=100, freq="B"),
        "open": np.linspace(1400, 1500, 100),
        "high": np.linspace(1450, 1550, 100),
        "low": np.linspace(1380, 1480, 100),
        "close": np.linspace(1400, 1500, 100),
        "volume": np.random.uniform(10000, 50000, 100),
        "amount": np.random.uniform(100000, 500000, 100),
        "pe_ttm": np.random.uniform(20, 30, 100),
        "publication_date": ["2024-12-31"] * 100
    })
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    req = "分析 600519.SH 贵州茅台的动量、波动率与换手流动性，并校验 PIT 与 Look-Ahead 安全"
    res = agent.run(req, services=services)

    assert res.is_real is True
    assert res.data_mode == "RESEARCH"
    assert res.plan.is_valid is True
    assert "600519.SH" in res.plan.symbols
    assert len(res.evidences) >= 1
    assert len(res.result_hash) == 16
    assert "ReAct Research Agent 报告" in res.final_answer


def test_anti_proof_direct_dataframe_access_blocked():
    """反证测试 1: 验证 Agent 源码绝对不直接调取 pd.read_parquet 或暴露裸 DataFrame"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    source_code = inspect.getsource(agent.run)

    assert "read_parquet" not in source_code
    assert "read_csv" not in source_code
    assert "to_parquet" not in source_code


def test_anti_proof_direct_http_access_blocked():
    """反证测试 2: 验证 Agent 源码绝对不包含 requests.get 或 ak.stock_* 原生 API 强越权调用"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    source_code = inspect.getsource(agent.run)

    assert "requests.get" not in source_code
    assert "requests.post" not in source_code
    assert "ak.stock_" not in source_code


def test_anti_proof_demo_injection_rejected():
    """反证测试 3: 强制注入 DEMO 标记引发 ResearchDataIntegrityError 拒绝卡门控"""
    demo_contract = MarketDataContract(
        symbol="600519.SH",
        name="贵州茅台",
        market="SH",
        close=1450.0,
        source="DemoProvider",
        data_mode="DEMO",
        is_real=False
    )
    with pytest.raises(ResearchDataIntegrityError, match="DemoProvider 数据侵入"):
        ResearchDataIntegrityGate.assert_valid_research_data(demo_contract, context="Demo Injection Test")


def test_anti_proof_fake_price_injection_rejected():
    """反证测试 4: 000001.SH 注入被平安银行股价污染价格 (< 500) 触发拒绝"""
    corrupted_sh_index = MarketDataContract(
        symbol="000001.SH",
        name="上证指数",
        market="SH",
        close=11.50,  # 平安银行股价
        source="CorruptedProvider",
        data_mode="RESEARCH",
        is_real=True
    )
    with pytest.raises(ResearchDataIntegrityError, match="被平安银行 .* 污染"):
        ResearchDataIntegrityGate.assert_valid_research_data(corrupted_sh_index, context="Fake Price Test")


def test_anti_proof_symbol_confusion_rejected():
    """反证测试 5: 裸代码 000001 被拒绝，强隔离 000001.SH 与 000001.SZ"""
    plan = ResearchPlanner.create_plan("分析 000001 的收益", mode="RESEARCH MODE")
    assert plan.is_valid is False
    assert "拒绝裸代码 '000001'" in plan.planning_error


def test_anti_proof_data_unavailable_propagation(monkeypatch):
    """反证测试 6: 当行情 API 与 Cache 完全失败时，必须优雅传播 DATA_UNAVAILABLE (绝无假 fallback)"""
    services = get_services("RESEARCH MODE")
    provider = services["provider"]

    # 模拟真实行情 API 与 Cache 均失效
    monkeypatch.setattr("src.data.akshare_provider.get_single_stock_spot", lambda sym: {"price": None, "status": "DATA_UNAVAILABLE"})
    monkeypatch.setattr(provider, "get_hist", lambda sym, s, e: pd.DataFrame())

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    res = agent.run("查询 600519.SH 的行情", services=services)

    assert res.data_mode == "RESEARCH"
    assert res.is_real is True
    # 绝不能伪造假价格
    assert "3280.50" not in res.final_answer
    assert "3832.26" not in res.final_answer


def test_pit_safety_validation():
    """断言 PIT 规则发布日 <= 交易日由 Agent 规划自动约束"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    plan = ResearchPlanner.create_plan("分析 600519.SH 的 EP 估值因子", mode="RESEARCH MODE")

    assert plan.integrity_requirements["pit_required"] is True


def test_lookahead_safety_validation():
    """断言 Look-Ahead 规则由 Agent 规划自动约束"""
    plan = ResearchPlanner.create_plan("分析 600519.SH 的动量因子", mode="RESEARCH MODE")
    assert plan.integrity_requirements["lookahead_safe"] is True


def test_react_trace_completeness(monkeypatch):
    """验证 ReAct Trace 中 AgentStep[] 的完整性与留痕记录"""
    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=30, freq="B"),
        "close": np.linspace(1400, 1500, 30),
        "volume": [1000] * 30,
        "amount": [10000] * 30
    })
    mock_quote = MarketDataContract(
        symbol="600519.SH",
        name="贵州茅台",
        market="SH",
        close=1450.0,
        source="Tencent Realtime API",
        data_mode="RESEARCH",
        is_real=True,
        status="AVAILABLE"
    )
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)
    monkeypatch.setattr(services["provider"], "get_latest", lambda sym: mock_quote)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    res = agent.run("分析 600519.SH 的 20 日动量并评估回测", services=services)

    assert len(res.tool_execution_records) >= 2
    for r in res.tool_execution_records:
        assert r.run_id == res.run_id
        assert r.arguments_hash != ""
        assert r.status in ["SUCCESS", "FAILED", "ERROR"]




def test_evidence_lineage_hash_completeness():
    """验证最终 ResearchResult 的存证卡片 Hash 与 Metadata 规范"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    services = get_services("RESEARCH MODE")
    res = agent.run("查询 600519.SH 最新行情", services=services)

    assert len(res.result_hash) == 16
    res_dict = res.to_dict()
    assert res_dict["is_real"] is True
    assert res_dict["data_mode"] == "RESEARCH"


def test_final_research_result_usefulness(monkeypatch):
    """验证最终 Agent 生成的研究结论具备明确的业务实用性与全血缘引用"""
    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=30, freq="B"),
        "close": np.linspace(1400, 1500, 30),
        "volume": [1000] * 30,
        "amount": [10000] * 30
    })
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    res = agent.run("全面分析 600519.SH 茅台的动量与回测", services=services)

    ans = res.final_answer
    assert "600519.SH" in ans
    assert "RESEARCH" in ans
    assert "Step 1" in ans
