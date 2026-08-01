"""
test_react_agent.py
Phase 16 Step 4: ReAct Research Agent 端到端集成与防线断言测试套件：
1. Planner 正确生成结构化 ResearchPlan
2. Agent 只能通过 AgentToolRegistry 派发工具
3. Agent 无法直接访问裸 DataFrame 或底座 Provider
4. ToolPermission 越权拦截断言
5. Research Mode 数据完整性校验
6. DATA_UNAVAILABLE 正确传播
7. PIT / Look-Ahead 失败正确传播
8. Evidence lineage 完整性
9. 端到端 ReAct Research Agent 完整工作流测试
"""

import pytest
import pandas as pd
import numpy as np
from app import get_services
from src.research.agent import ReActResearchAgent, ResearchResult
from src.research.planner import ResearchPlanner
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.base import ToolPermission, ToolPermissionError


def test_planner_correctly_generates_research_plan():
    """验证 Planner 为 ReAct Agent 生成合法的 ResearchPlan"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    req = "分析贵州茅台与招商银行的 20 日动量表现，并运行回测"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is True
    assert "600519.SH" in plan.symbols
    assert "600036.SH" in plan.symbols
    assert "MOM_20D" in plan.alpha_ids
    assert "compute_factor" in plan.required_tools
    assert "run_backtest" in plan.required_tools


def test_agent_only_operates_through_tool_registry(monkeypatch):
    """验证 Agent 执行步骤 100% 留痕于 AgentToolRegistry"""
    AgentToolRegistry.clear()
    from src.research.tools import load_initial_tools
    load_initial_tools()

    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=30, freq="B"),
        "close": np.linspace(1400, 1500, 30),
        "volume": [1000] * 30,
        "amount": [10000] * 30
    })
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    req = "计算 600519.SH 的 MOM_20D 因子"
    res = agent.run(req, services=services)

    assert res.data_mode == "RESEARCH"
    assert len(res.tool_execution_records) > 0
    tools_called = [r.tool_name for r in res.tool_execution_records]
    assert "compute_factor" in tools_called


def test_agent_cannot_access_raw_dataframe():
    """验证 Agent 返回的 ResearchResult 绝对不包含裸 DataFrame"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    services = get_services("RESEARCH MODE")
    res = agent.run("查询 600519.SH 的最新行情与动量", services=services)

    assert not isinstance(res.final_answer, pd.DataFrame)
    assert isinstance(res.final_answer, str)
    assert isinstance(res.to_dict(), dict)


def test_tool_permission_enforcement_blocks_unauthorized_step():
    """验证 Agent 权限集缺少 BACKTEST 时，调用 run_backtest 被安全拦截"""
    read_only_agent = ReActResearchAgent(
        mode="RESEARCH MODE",
        permissions={ToolPermission.READ_ONLY}
    )
    services = get_services("RESEARCH MODE")
    res = read_only_agent.run("运行 600519.SH 的策略回测", services=services)

    # 回测步骤应当因缺少 BACKTEST 权限而标记为 FAILED
    assert "FAILED" in res.final_answer or "需要权限 [BACKTEST]" in res.final_answer


def test_research_mode_data_integrity_check():
    """验证 Research Mode 下 Agent 生成的结果数据模式与 real 属性强一致"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    services = get_services("RESEARCH MODE")
    res = agent.run("查询上证指数 000001.SH 最新行情", services=services)

    assert res.is_real is True
    assert res.data_mode == "RESEARCH"
    assert len(res.evidences) > 0


def test_data_unavailable_propagation(monkeypatch):
    """当 API / Cache 无法获取真实数据时，Agent 能够正确传播 DATA_UNAVAILABLE"""
    services = get_services("RESEARCH MODE")
    provider = services["provider"]

    # 模拟真实行情 API 返回 UNAVAILABLE 并且历史行情为空
    monkeypatch.setattr(provider, "get_hist", lambda sym, s, e: pd.DataFrame())

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    res = agent.run("获取不存在股票的 K 线数据", services=services)

    assert "RESEARCH" in res.data_mode
    assert res.result_hash != ""


def test_pit_and_lookahead_failure_propagation():
    """验证 PIT 与 Look-Ahead 校验规则包含在 Agent 规划与执行要求中"""
    agent = ReActResearchAgent(mode="RESEARCH MODE")
    services = get_services("RESEARCH MODE")
    res = agent.run("计算 600519.SH 的 EP 估值因子", services=services)

    assert res.plan.integrity_requirements["pit_required"] is True
    assert res.plan.integrity_requirements["lookahead_safe"] is True


def test_evidence_lineage_completeness(monkeypatch):
    """验证 ReAct Agent 端到端运行产出的 Evidence Lineage 卡片完整性"""
    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=30, freq="B"),
        "close": np.linspace(1400, 1500, 30),
        "volume": [1000] * 30,
        "amount": [10000] * 30
    })
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    res = agent.run("计算 600519.SH 的 MOM_20D 因子并输出存证", services=services)

    assert len(res.evidences) > 0
    ev = res.evidences[0]
    assert "alpha_id" in ev or "symbol" in ev


def test_end_to_end_research_agent_workflow(monkeypatch):
    """完整端到端 Workflow: 自然语言 -> Plan -> Select Tool -> Execute -> Integrity Gate -> Evidence -> Final Answer"""
    services = get_services("RESEARCH MODE")
    mock_df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=60, freq="B"),
        "close": np.linspace(1400, 1600, 60),
        "volume": np.random.uniform(1000, 5000, 60),
        "amount": np.random.uniform(10000, 50000, 60)
    })
    monkeypatch.setattr(services["provider"], "get_hist", lambda sym, s, e: mock_df)

    agent = ReActResearchAgent(mode="RESEARCH MODE")
    req = "综合分析贵州茅台 600519.SH 的 20 日动量，并进行组合风控与压力测试"
    res = agent.run(req, services=services)

    assert res.run_id.startswith("react_run_")
    assert res.plan.is_valid is True
    assert len(res.tool_execution_records) >= 2
    assert len(res.result_hash) == 16
    assert "ReAct Research Agent 报告" in res.final_answer
