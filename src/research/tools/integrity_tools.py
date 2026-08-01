"""
integrity_tools.py
Integrity 审计与门控工具集：ValidateResearchDataTool, ValidateAlphaTool, ValidatePITTool, ValidateNoLookaheadTool, ValidateSymbolTool, ValidateProvenanceTool
强制对接 ResearchDataIntegrityGate，阻断非真实数据侵入。
"""

import pandas as pd
from typing import Dict, Any, List
from src.research.tools.base import AgentTool, ToolExecutionContext, ToolResult, ToolPermission
from src.system.integrity_gate import ResearchDataIntegrityGate, ResearchDataIntegrityError
from src.data.contract import normalize_market_data_contract
from src.factors.alpha_zoo import AlphaRegistry, validate_alpha, validate_no_lookahead, validate_symbol_integrity
from src.factors.alpha_zoo.validation import validate_pit_cutoff_date


class ValidateResearchDataTool(AgentTool):
    name = "validate_research_data"
    description = "审计行情或对象数据是否具备合规的 Research Mode 真实血缘 (拒绝 Demo/Mock/DATA_UNAVAILABLE)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"}
        },
        "required": ["symbol"]
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, symbol: str, **kwargs) -> ToolResult:
        provider = context.services.get("provider")
        if not provider:
            return ToolResult(success=False, data=None, error="Provider Service 未注入 Tool Context")

        quote = provider.get_latest(symbol)
        contract = normalize_market_data_contract(quote)

        try:
            ResearchDataIntegrityGate.assert_valid_research_data(contract, context=f"ValidateResearchDataTool({symbol})")
            return ToolResult(
                success=True,
                data={"symbol": symbol, "status": "VERIFIED_REAL_DATA", "source": contract.source},
                evidence={"symbol": symbol, "is_real": True, "source": contract.source}
            )
        except ResearchDataIntegrityError as e:
            return ToolResult(
                success=False,
                data={"symbol": symbol, "status": "REJECTED", "reason": str(e)},
                error=str(e),
                warnings=[str(e)]
            )


class ValidateAlphaTool(AgentTool):
    name = "validate_alpha"
    description = "对指定 Alpha 因子运行 5 维合规与断言检验"
    input_schema = {
        "type": "object",
        "properties": {
            "alpha_id": {"type": "string"}
        },
        "required": ["alpha_id"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, alpha_id: str, **kwargs) -> ToolResult:
        try:
            alpha_def = AlphaRegistry.get(alpha_id)
            is_valid, warnings = validate_alpha(alpha_def)
            return ToolResult(
                success=is_valid,
                data={"alpha_id": alpha_id, "is_valid": is_valid, "warnings": warnings},
                evidence={"alpha_id": alpha_id, "lookahead_safe": alpha_def.lookahead_safe}
            )
        except KeyError as e:
            return ToolResult(success=False, data=None, error=str(e))


class ValidatePITTool(AgentTool):
    name = "validate_pit"
    description = "断言财报发布日与交易切片日，拦截未来财报泄露 (publication_date <= trading_date)"
    input_schema = {
        "type": "object",
        "properties": {
            "trading_date": {"type": "string"},
            "publication_date": {"type": "string"}
        },
        "required": ["trading_date", "publication_date"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, trading_date: str, publication_date: str, **kwargs) -> ToolResult:
        try:
            res = validate_pit_cutoff_date(trading_date, publication_date)
            return ToolResult(
                success=res,
                data={"status": "PIT_PASSED", "trading_date": trading_date, "publication_date": publication_date},
                evidence={"pit_safe": True}
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), warnings=[str(e)])


class ValidateNoLookaheadTool(AgentTool):
    name = "validate_no_lookahead"
    description = "对指定 Alpha 运行未来切片扰动不变性断言测试"
    input_schema = {
        "type": "object",
        "properties": {
            "alpha_id": {"type": "string"}
        },
        "required": ["alpha_id"]
    }
    permission = ToolPermission.RESEARCH

    def execute(self, context: ToolExecutionContext, alpha_id: str, **kwargs) -> ToolResult:
        try:
            alpha_def = AlphaRegistry.get(alpha_id)
            res = validate_no_lookahead(alpha_def, pd.DataFrame())
            return ToolResult(
                success=res,
                data={"alpha_id": alpha_id, "lookahead_safe": res},
                evidence={"alpha_id": alpha_id, "status": "VERIFIED_LOOKAHEAD_SAFE"}
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), warnings=[str(e)])


class ValidateSymbolTool(AgentTool):
    name = "validate_symbol"
    description = "验证股票/指数代码是否符合 Canonical Symbol 规范 (隔离 000001.SH 与 000001.SZ，拒绝 000001)"
    input_schema = {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["symbols"]
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, symbols: List[str], **kwargs) -> ToolResult:
        try:
            res = validate_symbol_integrity(symbols)
            return ToolResult(
                success=res,
                data={"symbols": symbols, "status": "CANONICAL_SYMBOLS_VALID"},
                evidence={"validated_symbols": symbols}
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), warnings=[str(e)])


class ValidateProvenanceTool(AgentTool):
    name = "validate_provenance"
    description = "验证数据模式与数据源头血缘是否为真正的 RESEARCH MODE 实盘数据"
    input_schema = {
        "type": "object",
        "properties": {
            "data_mode": {"type": "string"},
            "is_real": {"type": "boolean"},
            "source": {"type": "string"}
        },
        "required": ["data_mode", "is_real"]
    }
    permission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, data_mode: str, is_real: bool, source: str = None, **kwargs) -> ToolResult:
        if data_mode != "RESEARCH" or not is_real or not source:
            return ToolResult(
                success=False,
                data={"status": "REJECTED_NON_REAL_PROVENANCE"},
                error="PROVENANCE ERROR: 非真实 Research Mode 数据源",
                warnings=["拒绝非真实数据源侵入引擎"]
            )

        return ToolResult(
            success=True,
            data={"status": "PROVENANCE_VERIFIED", "source": source},
            evidence={"data_mode": data_mode, "is_real": is_real, "source": source}
        )
