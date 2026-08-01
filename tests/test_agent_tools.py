"""
test_agent_tools.py
Phase 16 Step 3: Agent Tool Registry & Integrity Tools 测试套件
涵盖注册、鉴权、数据模式隔离、Integrity Gate 强断言、留痕存证、端到端集成测试等。
"""

import pytest
import pandas as pd
import numpy as np
from app import get_services
from src.research.tools import (
    AgentTool,
    AgentToolRegistry,
    ToolExecutionContext,
    ToolResult,
    ToolPermission,
    ToolPermissionError,
    load_initial_tools
)
from src.system.integrity_gate import ResearchDataIntegrityError


@pytest.fixture(autouse=True)
def reset_tool_registry():
    AgentToolRegistry.clear()
    load_initial_tools()


def test_tool_registry_register():
    tools = AgentToolRegistry.list_all()
    assert len(tools) >= 18
    names = [t.name for t in tools]
    assert "get_market_quote" in names
    assert "compute_factor" in names
    assert "run_backtest" in names
    assert "validate_research_data" in names


def test_tool_registry_duplicate_rejection():
    tool = AgentToolRegistry.get("get_market_quote")
    with pytest.raises(ValueError, match="已注册，禁止静默覆盖"):
        AgentToolRegistry.register(tool)


def test_tool_registry_unknown_tool():
    with pytest.raises(KeyError, match="未找到工具"):
        AgentToolRegistry.get("non_existent_tool")


def test_market_tool_uses_contract():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("get_market_quote", context, symbol="600519.SH")
    assert res.success is True
    assert res.data["symbol"] == "600519.SH"
    assert res.data["name"] == "贵州茅台"
    assert res.data["is_real"] is True
    assert res.evidence is not None


def test_market_tool_rejects_demo_data(monkeypatch):
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    # 模拟返回 Demo 标注对象
    class DemoQuote:
        symbol = "600519.SH"
        name = "贵州茅台"
        market = "SH"
        close = 1450.0
        source = "DemoMarketDataProvider"
        data_mode = "DEMO"
        is_real = False
        status = "AVAILABLE"

    provider = services["provider"]
    monkeypatch.setattr(provider, "get_latest", lambda sym: DemoQuote())

    res = AgentToolRegistry.execute("get_market_quote", context, symbol="600519.SH")
    assert res.success is False
    assert "DemoProvider 数据侵入" in res.error


def test_market_tool_rejects_non_real_data(monkeypatch):
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    class FakeQuote:
        symbol = "600519.SH"
        name = "贵州茅台"
        market = "SH"
        close = 1450.0
        source = "FakeSource"
        data_mode = "RESEARCH"
        is_real = False
        status = "AVAILABLE"

    provider = services["provider"]
    monkeypatch.setattr(provider, "get_latest", lambda sym: FakeQuote())

    res = AgentToolRegistry.execute("get_market_quote", context, symbol="600519.SH")
    assert res.success is False
    assert "非真实行情数据" in res.error


def test_market_tool_rejects_bare_symbol():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    class BareQuote:
        symbol = "000001"
        name = "未知"
        market = "SH"
        close = 10.0
        source = "Test"
        data_mode = "RESEARCH"
        is_real = True
        status = "AVAILABLE"

    provider = services["provider"]
    context.services["provider"].get_latest = lambda sym: BareQuote()

    res = AgentToolRegistry.execute("get_market_quote", context, symbol="000001")
    assert res.success is False
    assert "拒绝裸代码 '000001'" in res.error


def test_factor_tool_uses_alpha_registry():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("compute_factor", context, alpha_id="MOM_20D", symbols=["600519.SH"])
    assert res.success is True
    assert "600519.SH" in res.data
    assert res.evidence["alpha_id"] == "MOM_20D"


def test_factor_tool_generates_evidence():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("compute_factor", context, alpha_id="REV_20D", symbols=["000001.SZ"])
    assert res.success is True
    evidences = res.evidence["evidences"]
    assert len(evidences) == 1
    assert evidences[0]["symbol"] == "000001.SZ"
    assert evidences[0]["is_real"] is True


def test_factor_tool_rejects_invalid_alpha():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("compute_factor", context, alpha_id="INVALID_ALPHA", symbols=["600519.SH"])
    assert res.success is False
    assert "未找到 ID 为" in res.error


def test_integrity_tool_blocks_demo():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("validate_provenance", context, data_mode="DEMO", is_real=False, source="Demo")
    assert res.success is False
    assert "拒绝非真实数据源" in res.warnings[0]


def test_integrity_tool_blocks_future_data():
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH")

    res = AgentToolRegistry.execute("validate_pit", context, trading_date="2025-01-02", publication_date="2025-01-05")
    assert res.success is False
    assert "未来财报泄露拦截" in res.warnings[0]


def test_tool_permission_enforcement():
    # 模拟只有 READ_ONLY 权限受限的 Context
    restricted_context = ToolExecutionContext(
        mode="RESEARCH MODE",
        data_mode="RESEARCH",
        permissions={ToolPermission.READ_ONLY}
    )

    # 尝试调用需要 RESEARCH 权限的 compute_factor
    res = AgentToolRegistry.execute("compute_factor", restricted_context, alpha_id="MOM_20D", symbols=["600519.SH"])
    assert res.success is False
    assert "需要权限 [RESEARCH]" in res.error


def test_tool_execution_record_created():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services, run_id="run_test_123")

    AgentToolRegistry.execute("list_available_factors", context)
    records = AgentToolRegistry.get_execution_records()
    assert len(records) > 0
    latest = records[-1]
    assert latest.run_id == "run_test_123"
    assert latest.tool_name == "list_available_factors"
    assert latest.status == "SUCCESS"


def test_tool_result_has_evidence():
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services)

    res = AgentToolRegistry.execute("run_stress_test", context, portfolio_equity=1000000.0)
    assert res.success is True
    assert res.result_hash != ""
    assert res.evidence["scenarios_count"] > 0


def test_end_to_end_agent_tool_pipeline():
    """端到端: AgentToolRegistry -> Market Tool -> Research Provider -> MarketDataContract -> IntegrityGate -> Evidence"""
    services = get_services("RESEARCH MODE")
    context = ToolExecutionContext(mode="RESEARCH MODE", data_mode="RESEARCH", services=services, run_id="e2e_run_999")

    # 1. 查询行情
    r1 = AgentToolRegistry.execute("get_market_quote", context, symbol="600519.SH")
    assert r1.success is True

    # 2. 计算 Alpha
    r2 = AgentToolRegistry.execute("compute_factor", context, alpha_id="MOM_20D", symbols=["600519.SH"])
    assert r2.success is True

    # 3. 运行风控
    r3 = AgentToolRegistry.execute("run_stress_test", context)
    assert r3.success is True

    # 检查存证留痕链条
    records = AgentToolRegistry.get_execution_records()
    e2e_records = [rec for rec in records if rec.run_id == "e2e_run_999"]
    assert len(e2e_records) == 3
