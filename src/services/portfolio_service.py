"""
portfolio_service.py
组合与模拟交易服务层 (PortfolioService)
管理 PaperAccount Facade 与实操调仓，强保障 Service -> UI 统一 PortfolioSummary 契约。
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from src.execution.paper_trader import PaperAccount
from src.portfolio.contract import normalize_portfolio_summary, validate_portfolio_summary_contract


class PortfolioService:
    def __init__(self, account: Optional[PaperAccount] = None):
        self.account = account

    def get_portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        返回强契约 Portfolio Summary 字典，绝对包含全套 9 大维度与兜底默认值
        """
        current_prices = current_prices or {}
        try:
            raw_summary = self.account.get_summary(current_prices) if self.account else {}
        except Exception:
            raw_summary = {}

        normalized = normalize_portfolio_summary(raw_summary)
        return validate_portfolio_summary_contract(normalized, context_label="PortfolioService.get_portfolio_summary")

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
            self.account.reset_account(capital=initial_capital)
