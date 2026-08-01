"""
factor_tools.py
Factor 因子工具集：ListAvailableFactorsTool, ComputeFactorTool, CompareFactorsTool
对接到 AlphaRegistry 与 AlphaEvidenceRecord 存证。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.factors.alpha_zoo import AlphaRegistry
from src.factors.alpha_zoo.evidence import AlphaEvidenceRecord


class ListAvailableFactorsTool(AgentTool):
    name = "list_available_factors"
    description = "查询 AlphaRegistry 注册表中所有已审计可用的 Alpha 因子列表"
    input_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "可选分类，如 Momentum, Reversal, Volatility, Liquidity, Value"}
        }
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, category: str = None, **kwargs) -> ToolResult:
        if category:
            alphas = AlphaRegistry.list_by_category(category)
        else:
            alphas = AlphaRegistry.list_all()

        res = [a.to_dict() for a in alphas]
        return ToolResult(
            success=True,
            data=res,
            evidence={"total_factors": len(res), "category_filter": category}
        )


class ComputeFactorTool(AgentTool):
    name = "compute_factor"
    description = "对指定标的计算指定的 Alpha 因子值并输出 AlphaEvidenceRecord 存证卡片"
    input_schema = {
        "type": "object",
        "properties": {
            "alpha_id": {"type": "string", "description": "Alpha 唯一 ID, 如 'MOM_20D'"},
            "symbols": {"type": "array", "items": {"type": "string"}, "description": "标的代码列表，如 ['600519.SH']"}
        },
        "required": ["alpha_id", "symbols"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, alpha_id: str, symbols: List[str], **kwargs) -> ToolResult:
        try:
            alpha_def = AlphaRegistry.get(alpha_id)
        except KeyError as e:
            return ToolResult(success=False, data=None, error=str(e))

        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool Context")

        evidences = []
        res_data = {}

        for sym in symbols:
            df = provider.get_hist(sym, "2024-01-01", "2026-07-20")
            if df.empty:
                continue

            factor_series = AlphaRegistry.compute(alpha_id, df)
            latest_val = float(factor_series.dropna().iloc[-1]) if not factor_series.dropna().empty else None

            evidence = AlphaEvidenceRecord(
                alpha_id=alpha_id,
                symbol=sym,
                data_source="AkShare / Tencent API (RESEARCH)",
                data_start="2024-01-01",
                data_end="2026-07-20",
                data_mode=context.data_mode,
                is_real=(context.data_mode == "RESEARCH"),
                latest_value=latest_val
            )
            evidences.append(evidence.to_dict())
            res_data[sym] = latest_val

        return ToolResult(
            success=True,
            data=res_data,
            evidence={
                "alpha_id": alpha_id,
                "evidences": evidences
            }
        )


class CompareFactorsTool(AgentTool):
    name = "compare_factors"
    description = "横向对比多个 Alpha 因子在标的组合上的最新分值矩阵"
    input_schema = {
        "type": "object",
        "properties": {
            "alpha_ids": {"type": "array", "items": {"type": "string"}},
            "symbols": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["alpha_ids", "symbols"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, alpha_ids: List[str], symbols: List[str], **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool Context")

        matrix = {}
        for aid in alpha_ids:
            try:
                AlphaRegistry.get(aid)
            except KeyError:
                continue
            matrix[aid] = {}
            for sym in symbols:
                df = provider.get_hist(sym, "2024-01-01", "2026-07-20")
                if not df.empty:
                    s = AlphaRegistry.compute(aid, df)
                    val = float(s.dropna().iloc[-1]) if not s.dropna().empty else None
                    matrix[aid][sym] = val

        return ToolResult(
            success=True,
            data=matrix,
            evidence={"alpha_count": len(matrix), "symbol_count": len(symbols)}
        )
