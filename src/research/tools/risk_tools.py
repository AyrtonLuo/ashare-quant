"""
risk_tools.py
Risk 风控与压力测试工具集：GetPortfolioExposureTool, GetBarraExposureTool, RunStressTestTool
复用现有 Barra / ExposureCalculator 与 PortfolioStressTester 模块。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.risk_model.exposure import ExposureCalculator
from src.risk_model.decomposition import RiskDecomposer
from src.risk_model.stress_test import PortfolioStressTester


class GetPortfolioExposureTool(AgentTool):
    name = "get_portfolio_exposure"
    description = "获取投资组合在申万行业与风格因子上的暴露度"
    input_schema = {
        "type": "object",
        "properties": {
            "weights": {"type": "object", "description": "持仓权重字典，如 {'600519.SH': 0.5, '000001.SZ': 0.5}"}
        },
        "required": ["weights"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, weights: Dict[str, float], **kwargs) -> ToolResult:
        mock_fm = pd.DataFrame({
            "Value_EP": [0.05, 0.08],
            "Momentum_20D": [0.12, -0.05],
            "Volatility_20D": [0.15, 0.22],
            "Liquidity_20D": [0.50, 0.80],
            "Quality_ROE": [0.30, 0.12]
        }, index=list(weights.keys()))

        exp_data = ExposureCalculator.calculate_portfolio_exposures(weights, mock_fm)
        return ToolResult(
            success=True,
            data=exp_data,
            evidence={"weights": weights, "data_mode": context.data_mode}
        )


class GetBarraExposureTool(AgentTool):
    name = "get_barra_exposure"
    description = "计算组合在 6 大 Barra Style 风格因子与申万行业上的加权 Risk Decomposition"
    input_schema = {
        "type": "object",
        "properties": {
            "weights": {"type": "object"}
        },
        "required": ["weights"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, weights: Dict[str, float], **kwargs) -> ToolResult:
        decomp = RiskDecomposer.decompose_portfolio_risk(weights, pd.DataFrame())
        return ToolResult(
            success=True,
            data=decomp,
            evidence={"weights": weights, "total_volatility": decomp.get("total_volatility_annual")}
        )


class RunStressTestTool(AgentTool):
    name = "run_stress_test"
    description = "模拟大盘暴跌 -30% / 波动率 x1.5 / 流动性减半等极端行情下的组合压力测试"
    input_schema = {
        "type": "object",
        "properties": {
            "portfolio_equity": {"type": "number", "description": "组合总权益金额 (默认 1000000.0)"}
        }
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, portfolio_equity: float = 1000000.0, **kwargs) -> ToolResult:
        st_rep = PortfolioStressTester.run_stress_test(portfolio_equity=portfolio_equity)
        return ToolResult(
            success=True,
            data=st_rep.scenarios_results,
            evidence={"portfolio_equity": portfolio_equity, "scenarios_count": len(st_rep.scenarios_results)}
        )
