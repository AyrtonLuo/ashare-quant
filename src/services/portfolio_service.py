"""
portfolio_service.py
组合与模拟交易服务层 (PortfolioService)
管理 PaperAccount Facade 与实操调仓。
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from src.execution.paper_trader import PaperAccount


class PortfolioService:
    def __init__(self, account: PaperAccount):
        self.account = account

    def get_portfolio_summary(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        return self.account.get_summary(current_prices)

    def execute_rebalance(
        self,
        target_df: pd.DataFrame,
        market_regime_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self.account.rebalance(target_df, market_regime_info=market_regime_info)

    def reset_account(self, initial_capital: float = 1000000.0):
        self.account.reset_account(initial_capital=initial_capital)
