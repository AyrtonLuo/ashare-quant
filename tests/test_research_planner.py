"""
test_research_planner.py
Phase 16 Step 4A: ResearchPlanner & ResearchPlan Schema 测试套件
涵盖模式验证、工具注册校验、因子注册校验、裸代码拒绝、Demo/Mock 拒绝、PIT/Look-ahead 断言包含性测试等。
"""

import pytest
from src.research.planner import ResearchPlanner, ResearchPlan, PlanningError
from src.research.tools.registry import AgentToolRegistry
from src.factors.alpha_zoo.registry import AlphaRegistry


def test_natural_language_request_generates_valid_plan():
    """验证自然语言请求生成合法的结构化 ResearchPlan"""
    req = "分析贵州茅台过去一月的动量表现，并与沪深300比较"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is True
    assert plan.planning_error is None
    assert "600519.SH" in plan.symbols
    assert "MOM_20D" in plan.alpha_ids
    assert "compute_factor" in plan.required_tools
    assert len(plan.analysis_steps) >= 2


def test_research_plan_schema_validation():
    """验证 ResearchPlan 转字典后的完整字段模型"""
    plan = ResearchPlan(
        objective="测试目标",
        symbols=["600519.SH"],
        required_tools=["get_market_quote"],
        alpha_ids=["MOM_20D"]
    )
    p_dict = plan.to_dict()

    assert p_dict["objective"] == "测试目标"
    assert p_dict["symbols"] == ["600519.SH"]
    assert p_dict["integrity_requirements"]["data_mode"] == "RESEARCH"
    assert p_dict["integrity_requirements"]["pit_required"] is True
    assert p_dict["evidence_requirements"]["evidence_enabled"] is True


def test_planner_only_selects_registered_tools():
    """验证 Planner 规划的工具 100% 存在于 AgentToolRegistry 中"""
    req = "分析招商银行的动量与换手表现并运行回测"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is True
    for t_name in plan.required_tools:
        # AgentToolRegistry.get 如果不存在会抛 KeyError
        tool = AgentToolRegistry.get(t_name)
        assert tool is not None


def test_planner_only_selects_registered_alphas():
    """验证 Planner 规划的 Alpha 100% 存在于 AlphaRegistry 中"""
    req = "计算 600519.SH 的 EP_TTM 估值因子与 MOM_60D 动量"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is True
    for a_id in plan.alpha_ids:
        alpha_def = AlphaRegistry.get(a_id)
        assert alpha_def is not None


def test_bare_symbol_naked_code_rejected():
    """验证裸代码 000001 触发 Planner 明确规划拒绝"""
    req = "分析 000001 的动量表现"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is False
    assert "拒绝裸代码 '000001'" in plan.planning_error


def test_demo_mock_request_in_research_mode_rejected():
    """验证在 RESEARCH MODE 下要求 Demo / Mock / 模拟数据时触发拒绝"""
    req = "请使用 Demo 模拟假数据分析 600519.SH"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is False
    assert "严禁请求 Demo / Mock" in plan.planning_error


def test_research_mode_requirement_written_to_plan():
    """验证 Plan 中明确写入 data_mode = RESEARCH 断言要求"""
    req = "分析平安银行 000001.SZ 的收益"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.integrity_requirements["data_mode"] == "RESEARCH"
    assert plan.integrity_requirements["is_real"] is True


def test_pit_requirement_written_to_plan():
    """验证 Plan 中明确写入 PIT 断言要求"""
    req = "计算 600519.SH 的 EP 估值"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.integrity_requirements["pit_required"] is True


def test_lookahead_requirement_written_to_plan():
    """验证 Plan 中明确写入 Lookahead Safe 断言要求"""
    req = "分析贵州茅台的反转因子表现"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.integrity_requirements["lookahead_safe"] is True


def test_evidence_requirement_written_to_plan():
    """验证 Plan 中明确写入 Evidence 追踪要求"""
    req = "分析 600036.SH 的波动率与回测"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.evidence_requirements["evidence_enabled"] is True
    assert plan.evidence_requirements["hash_verification"] is True


def test_unexecutable_request_returns_explicit_planning_error():
    """验证无法执行的非研究请求返回明确的 planning_error"""
    req = "请预测明天涨停的股票并自动实盘下单"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is False
    assert "超出安全研究规划边界" in plan.planning_error


def test_planner_does_not_invoke_data_provider(monkeypatch):
    """验证 Planner 纯粹进行 Deterministic Planning，绝不上漏直接调用 Data Provider"""
    invoked = []

    def mock_get_latest(sym):
        invoked.append(sym)
        return None

    # 给 get_services 注入会打记录的 mock provider
    from app import get_services
    services = get_services("RESEARCH MODE")
    provider = services["provider"]
    monkeypatch.setattr(provider, "get_latest", mock_get_latest)

    req = "分析 600519.SH 与 000300.SH 的动量表现"
    plan = ResearchPlanner.create_plan(req, mode="RESEARCH MODE")

    assert plan.is_valid is True
    # 证明在 create_plan 执行期间，绝没有调用过 get_latest
    assert len(invoked) == 0
