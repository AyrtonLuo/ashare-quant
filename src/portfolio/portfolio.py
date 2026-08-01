"""
portfolio.py
核心组合管理器 (Portfolio)
贯通 Strategy -> Target Portfolio -> Order Generator -> Risk Check -> Execution Engine -> Position -> Accounting 全流程。
"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from src.portfolio.position import Position
from src.portfolio.order import Order, OrderSide, OrderStatus
from src.portfolio.execution import ExecutionEngine, TransactionCostModel
from src.portfolio.accounting import PortfolioAccounting

logger = logging.getLogger("portfolio")


class Portfolio:
    def __init__(self, initial_capital: float = 1000000.0):
        self.accounting = PortfolioAccounting(initial_capital=initial_capital, cash=initial_capital)
        self.positions: Dict[str, Position] = {}
        self.execution_engine = ExecutionEngine()
        self.orders_history: List[Order] = []
        self.last_trade_date: str = ""

    @property
    def cash(self) -> float:
        return self.accounting.cash

    @cash.setter
    def cash(self, val: float):
        self.accounting.cash = float(val)

    @property
    def initial_capital(self) -> float:
        return self.accounting.initial_capital

    def unfreeze_t1(self):
        """跨日把 T+1 冻结股份转为可用股份"""
        today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        if self.last_trade_date != today_str:
            for sym, pos in self.positions.items():
                pos.available_quantity = pos.quantity
            self.last_trade_date = today_str

    def submit_order(self, order: Order, price_limits: Optional[Dict[str, bool]] = None) -> Order:
        """
        提交订单进行撮合
        """
        self.unfreeze_t1()
        lim_up = price_limits.get("is_limit_up", False) if price_limits else False
        lim_down = price_limits.get("is_limit_down", False) if price_limits else False

        pos = self.positions.get(order.symbol, None)
        exec_order, new_cash, new_pos, pnl = self.execution_engine.validate_and_execute(
            order=order,
            cash=self.cash,
            position=pos,
            is_limit_up=lim_up,
            is_limit_down=lim_down
        )

        if exec_order.status == OrderStatus.FILLED:
            self.cash = new_cash
            self.accounting.realized_pnl += pnl
            if new_pos is None or new_pos.quantity <= 0:
                self.positions.pop(order.symbol, None)
            else:
                self.positions[order.symbol] = new_pos

        self.orders_history.append(exec_order)
        return exec_order

    def get_summary(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        计算账户总览
        """
        self.unfreeze_t1()
        for sym, pos in self.positions.items():
            if sym in current_prices:
                pos.market_price = float(current_prices[sym])

        summary = self.accounting.calculate(self.positions, current_prices)
        pos_records = [pos.to_dict() for pos in self.positions.values()]
        summary["positions"] = pos_records
        summary["positions_df"] = pd.DataFrame(pos_records) if pos_records else pd.DataFrame()
        summary["trade_logs"] = [o.to_dict() for o in self.orders_history]
        summary["trade_logs_df"] = pd.DataFrame(summary["trade_logs"]) if summary["trade_logs"] else pd.DataFrame()
        return summary
