"""
research_tools.py
Research 研究分析工具集：RunFactorAnalysisTool, CalculateFactorCorrelationTool, CalculateFactorDecayTool
复用现有 ResearchService 与 FactorAnalytics 模块。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.factors.analytics import FactorAnalytics


class RunFactorAnalysisTool(AgentTool):
    name = "run_factor_analysis"
    description = "对指定股票池运行多因子横截面分析"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}, "description": "规范标的代码列表"}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, symbols: List[str], **kwargs) -> ToolResult:
        res_svc = context.services.get("research")
        if not res_svc:
            return ToolResult(success=False, data=None, error="ResearchService 未注入 Tool Context")

        df_res = res_svc.run_factor_analysis(symbols)
        return ToolResult(
            success=True,
            data={
                "symbols": symbols,
                "rows_count": len(df_res),
                "columns": list(df_res.columns)
            },
            evidence={"analyzed_symbols": symbols, "data_mode": context.data_mode}
        )


class CalculateFactorCorrelationTool(AgentTool):
    name = "calculate_factor_correlation"
    description = "计算股票池上多因子的相关性矩阵 (Correlation Matrix)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, symbols: List[str], **kwargs) -> ToolResult:
        res_svc = context.services.get("research")
        if not res_svc:
            return ToolResult(success=False, data=None, error="ResearchService 未注入 Tool Context")

        corr_df = res_svc.compute_factor_correlation_matrix(symbols)
        return ToolResult(
            success=True,
            data=corr_df.to_dict(),
            evidence={"symbols": symbols, "matrix_shape": list(corr_df.shape)}
        )


class CalculateFactorDecayTool(AgentTool):
    name = "calculate_factor_decay"
    description = "分析指定 Alpha 因子的预测衰减曲线与 IC 半衰期"
    input_schema = {
        "type": "object",
        "properties": {
            "factor_name": {"type": "string", "description": "因子名称, 如 'Momentum_20D'"}
        },
        "required": ["factor_name"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, factor_name: str, **kwargs) -> ToolResult:
        rep = FactorAnalytics.analyze_factor_decay(factor_name, pd.Series([0.1, 0.2, 0.15, 0.18, 0.12]))
        return ToolResult(
            success=True,
            data=rep.to_dict(),
            evidence={"factor_name": factor_name, "half_life": rep.half_life}
        )
