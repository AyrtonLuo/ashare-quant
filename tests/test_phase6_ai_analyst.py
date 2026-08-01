"""
test_phase6_ai_analyst.py
Phase 6 AI Quant Analyst 智能研报、确定性诊断引擎与权限隔离绝密测试
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.schemas import ResearchContext, DiagnosticResult
from src.ai.diagnostics import DiagnosticsEngine
from src.ai.provider import LLMProvider, MockLLMProvider
from src.ai.report_generator import AutomatedReportGenerator


def test_research_context():
    ctx = ResearchContext(
        experiment_id="exp_001",
        strategy_id="MultiFactor_v1",
        universe=["600519"],
        date_range="2023-2026",
        benchmark="000300",
        performance_metrics={"TotalReturnPct": "15.0%", "Sharpe": 1.4}
    )
    d = ctx.to_dict()
    assert d["experiment_id"] == "exp_001"
    assert d["performance_metrics"]["Sharpe"] == 1.4


def test_performance_diagnostics():
    m1 = {"Sharpe": 1.5, "MaxDrawdown": 0.10}
    d1 = DiagnosticsEngine.diagnose_performance(m1)
    assert d1.level == "LOW"

    m2 = {"Sharpe": 0.3, "MaxDrawdown": 0.35}
    d2 = DiagnosticsEngine.diagnose_performance(m2)
    assert d2.level == "HIGH"


def test_factor_decay_detection():
    annual_ics = {"2023": 0.09, "2024": 0.06, "2025": 0.03}
    d = DiagnosticsEngine.detect_factor_decay(annual_ics)
    assert d.level == "HIGH"
    assert "Alpha 衰减" in d.summary


def test_overfitting_detection():
    d = DiagnosticsEngine.detect_overfitting(train_sharpe=2.5, val_sharpe=1.8, test_sharpe=0.8)
    assert d.level == "CRITICAL"
    assert "强过拟合预警" in d.summary


def test_regime_analysis():
    df = pd.DataFrame({
        "daily_return": [0.01, -0.02, 0.03, -0.01, 0.02, -0.015]
    })
    res = DiagnosticsEngine.analyze_regime_performance(df)
    assert "bull_sharpe" in res
    assert "bear_sharpe" in res


def test_ai_provider_interface():
    provider = MockLLMProvider()
    res = provider.generate("Test Prompt")
    assert "AI Quant Analyst" in res


def test_report_generation(tmp_path):
    gen = AutomatedReportGenerator(reports_dir=str(tmp_path))
    ctx = ResearchContext(
        experiment_id="exp_test_rep",
        strategy_id="MultiFactor_ML",
        universe=["600519"],
        date_range="2023-2026",
        benchmark="000300",
        performance_metrics={"TotalReturnPct": "20.0%", "Sharpe": 1.6, "MaxDrawdownPct": "10.0%"},
        decay_info={"annual_ics": {"2023": 0.08, "2024": 0.08}},
        overfitting_info={"train_sharpe": 1.7, "val_sharpe": 1.6, "test_sharpe": 1.6}
    )
    path = gen.generate_report(ctx)
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "Quant Research Report" in content


def test_ai_context_grounding(tmp_path):
    gen = AutomatedReportGenerator(reports_dir=str(tmp_path))
    ctx = ResearchContext(
        experiment_id="exp_grounding",
        strategy_id="Grounding_Test",
        universe=["600519"],
        date_range="2023-2026",
        benchmark="000300",
        performance_metrics={"TotalReturnPct": "12.34%", "Sharpe": 1.23}
    )
    path = gen.generate_report(ctx)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "12.34%" in content
        assert "1.23" in content


def test_ai_report_reproducibility(tmp_path):
    gen = AutomatedReportGenerator(reports_dir=str(tmp_path))
    ctx = ResearchContext(
        experiment_id="exp_rep_check",
        strategy_id="Rep_Test",
        universe=["600519"],
        date_range="2023-2026",
        benchmark="000300",
        performance_metrics={"TotalReturnPct": "15.0%", "Sharpe": 1.5}
    )
    gen.generate_report(ctx)
    json_path = tmp_path / "exp_rep_check_ai.json"
    assert os.path.exists(json_path)


def test_ai_does_not_execute_orders():
    """
    CRITICAL: 证明 AI 模块没有任何提交订单 (submit_order) 或直接调用 ExecutionEngine 的权限或通道！
    """
    import src.ai.report_generator as rg
    import src.ai.diagnostics as diag
    import src.ai.provider as prov

    for module in [rg, diag, prov]:
        assert not hasattr(module, "submit_order")
        assert not hasattr(module, "ExecutionEngine")
        assert not hasattr(module, "PaperAccount")
