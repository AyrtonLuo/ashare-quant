"""
portfolio_service.py
组合与模拟交易服务层 (PortfolioService)
管理 PaperAccount Facade 与实操调仓，强保障 Service -> UI 统一 PortfolioSummary 契约。
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from src.execution.paper_trader import PaperAccount


class PortfolioService:
    def __init__(self, account: PaperAccount):
        self.account = account

    def get_portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        返回强契约 Portfolio Summary 字典，绝对包含全套维度与兜底默认值
        """
        current_prices = current_prices or {}
        default_pos_df = pd.DataFrame(columns=[
            "股票代码", "股票名称", "总持股数", "可卖股份 (T+1)", "今日买入冻结", "持仓成本价", "最新价", "持仓市值", "浮动盈亏 %"
        ])

        try:
            summary = self.account.get_summary(current_prices) if self.account else {}
        except Exception:
            summary = {}

        initial_cap = float(summary.get("initial_capital", getattr(self.account, "initial_capital", 1000000.0)))
        cash = float(summary.get("cash", getattr(self.account, "cash", initial_cap)))
        mv = float(summary.get("market_value", 0.0))
        tot_eq = float(summary.get("total_equity", summary.get("equity", cash + mv)))
        tot_ret = float(summary.get("total_return_pct", summary.get("pnl_pct", (tot_eq - initial_cap) / initial_cap * 100.0 if initial_cap > 0 else 0.0)))
        pnl_pct = float(summary.get("pnl_pct", tot_ret))

        pos_df = summary.get("positions_df")
        if pos_df is None or not isinstance(pos_df, pd.DataFrame):
            pos_df = default_pos_df

        trade_logs_df = summary.get("trade_logs_df")
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

    def execute_rebalance(
        self,
        target_df: pd.DataFrame,
        market_regime_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.account:
            return {"status": "error", "message": "No account initialized"}
        return self.account.rebalance(target_df, market_regime_info=market_regime_info)

    def reset_account(self, initial_capital: float = 1000000.0):
        if self.account:
            self.account.reset_account(initial_capital=initial_capital)
