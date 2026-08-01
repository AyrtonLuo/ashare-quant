"""
backtest_tools.py
Backtest 回测工具集：RunBacktestTool, RunWalkForwardTool, CompareStrategiesTool
复用现有 BacktestService / WalkForwardRunner / BenchmarkComparisonSuite 模块。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.strategy.ma_cross_strategy import MACrossStrategy
from src.strategy.walk_forward import WalkForwardRunner
from src.benchmarks.suite import BenchmarkComparisonSuite


class RunBacktestTool(AgentTool):
    name = "run_backtest"
    description = "对指定策略与股票池运行 A 股全历史无未来函数回测 (包含真实印花税/佣金/过户费/滑点)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.BACKTEST

    def execute(self, context: ToolExecutionContext, symbols: List[str], start_date: str = "2023-01-01", end_date: str = "2026-07-20", **kwargs) -> ToolResult:
        bt_svc = context.services.get("backtest")
        if not bt_svc:
            return ToolResult(success=False, data=None, error="BacktestService 未注入 Tool Context")

        strat = MACrossStrategy(symbols)
        hist_df, perf = bt_svc.run_backtest(strat, symbols, start_date, end_date)

        return ToolResult(
            success=True,
            data={
                "performance": perf,
                "history_bars": len(hist_df),
                "symbols": symbols
            },
            evidence={
                "sharpe": perf.get("Sharpe"),
                "total_return": perf.get("TotalReturnPct"),
                "max_drawdown": perf.get("MaxDrawdownPct"),
                "data_mode": context.data_mode
            }
        )


class RunWalkForwardTool(AgentTool):
    name = "run_walk_forward"
    description = "执行 Walk-Forward 样本外 (OOS) 滚动交叉验证，评估策略时间维度的稳定性"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.BACKTEST

    def execute(self, context: ToolExecutionContext, symbols: List[str], **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool Context")

        wf_rep = WalkForwardRunner.run_walk_forward_validation(MACrossStrategy, symbols, provider)
        return ToolResult(
            success=True,
            data=wf_rep.to_dict(),
            evidence={
                "mean_oos_sharpe": wf_rep.mean_oos_sharpe,
                "is_time_stable": wf_rep.is_time_stable,
                "data_mode": context.data_mode
            }
        )


class CompareStrategiesTool(AgentTool):
    name = "compare_strategies"
    description = "对比 7 大策略基准全矩阵 (Buy&Hold / CSI300 / CSI1000 / EqualWeight / Momentum / MultiFactor / ML)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.BACKTEST

    def execute(self, context: ToolExecutionContext, symbols: List[str], **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool Context")

        bench_df = BenchmarkComparisonSuite.run_full_benchmark_comparison(symbols, provider)
        return ToolResult(
            success=True,
            data=bench_df.to_dict(),
            evidence={"benchmark_count": len(bench_df), "data_mode": context.data_mode}
        )
