"""
__init__.py
Agent Tools 模块初始化与所有 Approved Tools 自动注册
"""

from src.research.tools.base import (
    AgentTool,
    ToolExecutionContext,
    ToolResult,
    ToolExecutionRecord,
    ToolPermission,
    ToolPermissionError
)
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.market_tools import GetMarketQuoteTool, GetHistoricalPricesTool, GetIndexSnapshotTool
from src.research.tools.factor_tools import ListAvailableFactorsTool, ComputeFactorTool, CompareFactorsTool
from src.research.tools.research_tools import RunFactorAnalysisTool, CalculateFactorCorrelationTool, CalculateFactorDecayTool
from src.research.tools.risk_tools import GetPortfolioExposureTool, GetBarraExposureTool, RunStressTestTool
from src.research.tools.backtest_tools import RunBacktestTool, RunWalkForwardTool, CompareStrategiesTool
from src.research.tools.integrity_tools import (
    ValidateResearchDataTool,
    ValidateAlphaTool,
    ValidatePITTool,
    ValidateNoLookaheadTool,
    ValidateSymbolTool,
    ValidateProvenanceTool
)

INITIAL_TOOLS = [
    GetMarketQuoteTool(),
    GetHistoricalPricesTool(),
    GetIndexSnapshotTool(),
    ListAvailableFactorsTool(),
    ComputeFactorTool(),
    CompareFactorsTool(),
    RunFactorAnalysisTool(),
    CalculateFactorCorrelationTool(),
    CalculateFactorDecayTool(),
    GetPortfolioExposureTool(),
    GetBarraExposureTool(),
    RunStressTestTool(),
    RunBacktestTool(),
    RunWalkForwardTool(),
    CompareStrategiesTool(),
    ValidateResearchDataTool(),
    ValidateAlphaTool(),
    ValidatePITTool(),
    ValidateNoLookaheadTool(),
    ValidateSymbolTool(),
    ValidateProvenanceTool()
]


def load_initial_tools():
    """装载核心 Approved Agent Tools"""
    for tool in INITIAL_TOOLS:
        try:
            AgentToolRegistry.register(tool)
        except Exception:
            pass


load_initial_tools()

__all__ = [
    "AgentTool",
    "AgentToolRegistry",
    "ToolExecutionContext",
    "ToolResult",
    "ToolExecutionRecord",
    "ToolPermission",
    "ToolPermissionError",
    "load_initial_tools"
]
