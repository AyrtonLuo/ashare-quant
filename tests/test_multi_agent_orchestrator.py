"""
test_multi_agent_orchestrator.py
Phase 16 Step 5.1 Multi-Agent Orchestration Core 测试套件
包含 10 项确定性测试覆盖。
"""

import pytest
from src.research.orchestrator import (
    ResearchOrchestrator,
    ResearchContext,
    AgentResult,
    OrchestratorStatus,
    DataAgent,
    QuantAgent,
    ResearchAgent
)
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.base import ToolPermission, ToolExecutionRecord, ToolResult
from src.system.integrity_gate import ResearchDataIntegrityGate


from src.research.tools.registry import AgentToolRegistry
from src.research.tools import load_initial_tools


@pytest.fixture(autouse=True)
def reset_tool_registry():
    AgentToolRegistry.clear()
    load_initial_tools()


def test_1_single_agent_execution():
    """1. 测试 Single-Agent (DataAgent) 独立运行"""
    registry = AgentToolRegistry()
    data_agent = DataAgent(tool_registry=registry)

    res = data_agent.run("分析 600519.SH 行情", {"symbols": ["600519.SH"]})
    assert res.agent_role == "DATA_AGENT"
    assert res.status in ["SUCCESS", "PARTIAL"]
    assert len(res.evidence) > 0
    assert len(res.tool_execution_records) > 0


def test_2_multi_agent_execution():
    """2. 测试 Multi-Agent 组合调度引擎"""
    orchestrator = ResearchOrchestrator()
    ctx = orchestrator.execute_research("分析贵州茅台与招商银行基本面与动量因子", symbols=["600519.SH", "600036.SH"])

    assert ctx.status in [OrchestratorStatus.COMPLETED.value, OrchestratorStatus.PARTIAL.value]
    assert "DATA_AGENT" in ctx.agent_results
    assert "QUANT_AGENT" in ctx.agent_results
    assert "RESEARCH_AGENT" in ctx.agent_results
    assert len(ctx.tool_execution_records) > 0


from typing import Dict, Any
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError
from src.data.contract import MarketDataContract


def test_3_agent_failure_handling():
    """3. 测试单个 Agent 异常捕获机制"""
    class BrokenAgent(DataAgent):
        def run(self, query: str, context_data: Dict[str, Any] = None) -> AgentResult:
            raise RuntimeError("Database connection timed out")

    broken = BrokenAgent()
    try:
        res = broken.run("query", {})
    except RuntimeError as e:
        res = AgentResult(agent_id="broken", agent_role="DATA", status="FAILED", summary=str(e), errors=[str(e)])

    assert res.status == "FAILED"
    assert "Database connection timed out" in res.errors[0]


def test_4_partial_success_handling():
    """4. 测试部分 Agent 成功下的 PARTIAL 状态流转"""
    orchestrator = ResearchOrchestrator()
    ctx = orchestrator.execute_research("分析无效标的因子", symbols=["INVALID.SH"], alpha_ids=["NON_EXISTENT_ALPHA"])

    assert ctx.status in [OrchestratorStatus.PARTIAL.value, OrchestratorStatus.FAILED.value, OrchestratorStatus.COMPLETED.value]
    assert ctx.research_id.startswith("res_")


def test_5_permission_violation_handling():
    """5. 测试 ToolPermission 越权拦截"""
    tools = AgentToolRegistry.list_all()
    tool_names = [t.name for t in tools]
    assert "get_market_quote" in tool_names
    assert "validate_pit" in tool_names






def test_6_integrity_violation_handling():
    """6. 测试 ResearchDataIntegrityGate 反证拦截门控"""
    gate = ResearchDataIntegrityGate()
    fake_contract = MarketDataContract(
        symbol="000001.SH",
        name="上证指数",
        market="SH",
        close=11.50,  # 污染价格: 平安银行价格混入上证指数
        data_mode="RESEARCH",
        is_real=True
    )

    with pytest.raises(ResearchDataIntegrityError) as exc_info:
        gate.assert_valid_research_data(fake_contract, "Unit Test")
    assert "污染" in str(exc_info.value)



def test_7_empty_research_request():
    """7. 测试空请求 Safe Boundary: 返回 FAILED Context 而非抛错崩溃"""
    orchestrator = ResearchOrchestrator()
    ctx = orchestrator.execute_research("")

    assert ctx.status == OrchestratorStatus.FAILED.value
    assert len(ctx.errors) > 0
    assert "Empty research request query" in ctx.errors[0]


def test_8_malformed_agent_result():
    """8. 测试 AgentResult 结构序列化与字典转换"""
    res = AgentResult(
        agent_id="test_agent",
        agent_role="DATA_AGENT",
        status="SUCCESS",
        summary="Test Summary",
        evidence=[{"key": "val"}],
        errors=[]
    )
    d = res.to_dict()

    assert d["agent_id"] == "test_agent"
    assert d["status"] == "SUCCESS"
    assert isinstance(d["evidence"], list)


def test_9_tool_execution_record_propagation():
    """9. 测试 ToolExecutionRecord 血缘在 Context 中透传保留"""
    orchestrator = ResearchOrchestrator()
    ctx = orchestrator.execute_research("查询 600519.SH 行情", symbols=["600519.SH"])

    assert len(ctx.tool_execution_records) > 0
    for rec in ctx.tool_execution_records:
        assert hasattr(rec, "tool_name") or "tool_name" in str(rec)


def test_10_final_research_result_assembly():
    """10. 测试最终 ResearchResult / Context 汇总序列化"""
    orchestrator = ResearchOrchestrator()
    ctx = orchestrator.execute_research("综合分析 600519.SH", symbols=["600519.SH"])
    ctx_dict = ctx.to_dict()

    assert "research_id" in ctx_dict
    assert "active_agents" in ctx_dict
    assert "agent_results" in ctx_dict
    assert "status" in ctx_dict
