"""
contract.py
PortfolioSummaryContract 数据契约与标准化规范 (PortfolioSummaryContract)
为全系统提供统一的 PortfolioSummary 契约校验与 Normalization 引擎。
在 Service 层与 UI 层双重强制校验，确保 9 大维度字段绝对不缺失。
"""

import pandas as pd
from typing import Dict, Any, List, Optional


REQUIRED_PORTFOLIO_SUMMARY_KEYS = [
    "initial_capital",
    "cash",
    "market_value",
    "total_equity",
    "equity",
    "total_return_pct",
    "pnl_pct",
    "positions_df",
    "trade_logs_df"
]


class PortfolioContractError(Exception):
    """当 Portfolio Summary 契约校验不通过时抛出的明确可诊断异常"""
    pass


def normalize_portfolio_summary(raw_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    归一化与强契约补齐函数 (Normalization Pipeline)
    无论传入 None、空字典、还是缺少字段的旧数据结构，均规范化输出包含完整 9 大维度的字典。
    """
    raw_summary = raw_summary if isinstance(raw_summary, dict) else {}

    default_pos_df = pd.DataFrame(columns=[
        "股票代码", "股票名称", "总持股数", "可卖股份 (T+1)", "今日买入冻结", "持仓成本价", "最新价", "持仓市值", "浮动盈亏 %"
    ])

    initial_cap = float(raw_summary.get("initial_capital", 1000000.0))
    cash = float(raw_summary.get("cash", initial_cap))
    mv = float(raw_summary.get("market_value", 0.0))
    tot_eq = float(raw_summary.get("total_equity", raw_summary.get("equity", cash + mv)))

    # 计算或补齐 total_return_pct 与 pnl_pct
    if "total_return_pct" in raw_summary:
        tot_ret = float(raw_summary["total_return_pct"])
    elif "pnl_pct" in raw_summary:
        tot_ret = float(raw_summary["pnl_pct"])
    else:
        tot_ret = (tot_eq - initial_cap) / initial_cap * 100.0 if initial_cap > 0 else 0.0

    pnl_pct = float(raw_summary.get("pnl_pct", tot_ret))

    pos_df = raw_summary.get("positions_df")
    if pos_df is None or not isinstance(pos_df, pd.DataFrame):
        pos_df = default_pos_df

    trade_logs_df = raw_summary.get("trade_logs_df")
    if trade_logs_df is None or not isinstance(trade_logs_df, pd.DataFrame):
        trade_logs_df = pd.DataFrame()

    return {
        "initial_capital": round(initial_cap, 2),
        "cash": round(cash, 2),
        "market_value": round(mv, 2),
        "total_equity": round(tot_eq, 2),
        "equity": round(tot_eq, 2),
        "total_return_pct": round(tot_ret, 2),
        "pnl_pct": round(pnl_pct, 2),
        "positions_df": pos_df,
        "trade_logs_df": trade_logs_df
    }


def validate_portfolio_summary_contract(summary: Dict[str, Any], context_label: str = "Service -> UI") -> Dict[str, Any]:
    """
    强契约断言与校验函数
    检查 9 大必选字段是否存在。如果缺少任何字段，直接抛出带有上下文诊信息的 PortfolioContractError。
    """
    if not isinstance(summary, dict):
        raise PortfolioContractError(f"[{context_label}] Summary 数据结构非字典类型: {type(summary)}")

    missing_keys = [k for k in REQUIRED_PORTFOLIO_SUMMARY_KEYS if k not in summary]
    if missing_keys:
        raise PortfolioContractError(
            f"[{context_label}] Portfolio Summary 契约破损！缺失必填字段: {missing_keys}。已存在字段: {list(summary.keys())}"
        )

    return summary
