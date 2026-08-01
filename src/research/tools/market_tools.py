"""
market_tools.py
Market 行情工具集：GetMarketQuoteTool, GetHistoricalPricesTool, GetIndexSnapshotTool
强制走 MarketDataContract 与 ResearchDataIntegrityGate，防数据污染。
"""

from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.data.contract import normalize_market_data_contract
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError


from src.factors.alpha_zoo.validation import validate_symbol_integrity, AlphaValidationError


class GetMarketQuoteTool(AgentTool):
    name = "get_market_quote"
    description = "获取指定 A 股股票或指数的最新实时/盘后行情数据"
    input_schema = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "规范代码，如 '600519.SH' 或 '000001.SH'"}
        },
        "required": ["symbol"]
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, symbol: str, **kwargs) -> ToolResult:
        try:
            validate_symbol_integrity([symbol])
        except AlphaValidationError as e:
            return ToolResult(success=False, data=None, error=str(e), warnings=[str(e)])

        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool 上下文")


        raw_quote = provider.get_latest(symbol)
        contract = normalize_market_data_contract(raw_quote)

        # 强门控校验
        if context.data_mode == "RESEARCH":
            ResearchDataIntegrityGate.assert_valid_research_data(contract, context=f"GetMarketQuoteTool({symbol})")

        return ToolResult(
            success=(contract.status == "AVAILABLE"),
            data=contract.to_dict(),
            evidence={
                "symbol": contract.symbol,
                "name": contract.name,
                "close": contract.close,
                "source": contract.source,
                "status": contract.status,
                "is_real": contract.is_real
            }
        )


class GetHistoricalPricesTool(AgentTool):
    name = "get_historical_prices"
    description = "获取指定标的的历史 K 线数据 (OHLCV)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "规范代码，如 '600519.SH'"},
            "start_date": {"type": "string", "description": "起始日期 (YYYY-MM-DD)"},
            "end_date": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"}
        },
        "required": ["symbol"]
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, symbol: str, start_date: str = "2023-01-01", end_date: str = "2026-07-20", **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Context")

        df = provider.get_hist(symbol, start_date, end_date)
        if df.empty:
            return ToolResult(
                success=False,
                data=None,
                warnings=[f"标的 [{symbol}] 在指定区间无历史行情"],
                error="DATA_UNAVAILABLE"
            )

        return ToolResult(
            success=True,
            data={
                "symbol": symbol,
                "count": len(df),
                "start": start_date,
                "end": end_date,
                "columns": list(df.columns)
            },
            evidence={
                "symbol": symbol,
                "bars_count": len(df),
                "data_mode": context.data_mode
            }
        )


class GetIndexSnapshotTool(AgentTool):
    name = "get_index_snapshot"
    description = "获取核心大盘指数快照 (000001.SH 上证指数 / 000300.SH 沪深300 / 000852.SH 中证1000)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}}
        }
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, symbols: List[str] = None, **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Context")

        target_syms = symbols or ["000001.SH", "000300.SH", "000852.SH"]
        res = []

        for s in target_syms:
            q = provider.get_latest(s)
            c = normalize_market_data_contract(q)
            if context.data_mode == "RESEARCH":
                try:
                    ResearchDataIntegrityGate.assert_valid_research_data(c, context=f"GetIndexSnapshotTool({s})")
                except ResearchDataIntegrityError as e:
                    c.status = "UNAVAILABLE"
                    c.close = None
                    c.is_real = False
            res.append(c.to_dict())

        return ToolResult(
            success=True,
            data=res,
            evidence={"index_count": len(res), "data_mode": context.data_mode}
        )
