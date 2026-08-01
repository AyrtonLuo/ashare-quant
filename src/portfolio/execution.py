"""
execution.py
A 股规则撮合与交易成本引擎 (TransactionCostModel, ExecutionEngine)
支持 100 股一手整取、T+1 可卖校验、印花税与佣金拆算、涨跌停成交限制。
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
from src.portfolio.order import Order, OrderSide, OrderStatus
from src.portfolio.position import Position

logger = logging.getLogger("execution_engine")


@dataclass
class TransactionCostModel:
    commission_rate: float = 0.00025   # 0.025% 买卖佣金
    stamp_tax_rate: float = 0.0005      # 0.05% 卖出印花税
    slippage: float = 0.0              # 滑点

    def calculate_cost(self, side: OrderSide, price: float, quantity: int) -> Tuple[float, float, float]:
        """
        计算交易规费：(commission, stamp_tax, total_fees)
        """
        trade_val = price * quantity
        comm = trade_val * self.commission_rate
        tax = (trade_val * self.stamp_tax_rate) if side == OrderSide.SELL else 0.0
        total_fees = comm + tax
        return comm, tax, total_fees


class ExecutionEngine:
    def __init__(self, cost_model: Optional[TransactionCostModel] = None):
        self.cost_model = cost_model or TransactionCostModel()

    def validate_and_execute(
        self,
        order: Order,
        cash: float,
        position: Optional[Position] = None,
        is_limit_up: bool = False,
        is_limit_down: bool = False
    ) -> Tuple[Order, float, Optional[Position], float]:
        """
        撮合验证并执行订单：
        返回: (executed_order, new_cash, new_position, realized_pnl)
        """
        code = order.symbol
        price = order.price
        qty = order.quantity

        if qty <= 0 or price <= 0:
            order.status = OrderStatus.REJECTED
            order.reason = "无效的买卖股数或参考价格"
            return order, cash, position, 0.0

        # A 股 100 股一手整约束
        if qty % 100 != 0:
            qty = (qty // 100) * 100
            if qty <= 0:
                order.status = OrderStatus.REJECTED
                order.reason = "交易股数不足 1 手 (100 股)"
                return order, cash, position, 0.0
            order.quantity = qty

        realized_pnl = 0.0

        if order.side == OrderSide.BUY:
            if is_limit_up:
                order.status = OrderStatus.REJECTED
                order.reason = "目标标的今日封死涨停，挂单无法撮合"
                return order, cash, position, 0.0

            comm, tax, total_fees = self.cost_model.calculate_cost(OrderSide.BUY, price, qty)
            req_cash = price * qty + total_fees

            if cash < req_cash:
                max_lots = int((cash / (price * 100 * (1 + self.cost_model.commission_rate))))
                qty = max_lots * 100
                if qty <= 0:
                    order.status = OrderStatus.REJECTED
                    order.reason = "可用现金不足以购买 1 手 (100 股)"
                    return order, cash, position, 0.0
                order.quantity = qty
                comm, tax, total_fees = self.cost_model.calculate_cost(OrderSide.BUY, price, qty)
                req_cash = price * qty + total_fees

            new_cash = cash - req_cash
            order.status = OrderStatus.FILLED
            order.filled_quantity = qty
            order.filled_price = price

            if position is None:
                new_pos = Position(
                    symbol=code,
                    quantity=qty,
                    available_quantity=0,  # 今日买入 T+1 冻结
                    average_cost=price,
                    market_price=price
                )
            else:
                old_tot = position.quantity
                old_cost = position.average_cost
                new_tot = old_tot + qty
                new_cost = (old_cost * old_tot + price * qty) / new_tot
                new_pos = Position(
                    symbol=code,
                    quantity=new_tot,
                    available_quantity=position.available_quantity,
                    average_cost=new_cost,
                    market_price=price,
                    name=position.name
                )
            return order, new_cash, new_pos, 0.0

        elif order.side == OrderSide.SELL:
            if is_limit_down:
                order.status = OrderStatus.REJECTED
                order.reason = "目标标的今日封死跌停，卖单砸盘锁死无法撮合"
                return order, cash, position, 0.0

            if position is None or position.available_quantity < qty:
                avail = position.available_quantity if position else 0
                qty = (avail // 100) * 100
                if qty <= 0:
                    order.status = OrderStatus.REJECTED
                    order.reason = "持仓中可用 (T+1) 股份不足 1 手"
                    return order, cash, position, 0.0
                order.quantity = qty

            comm, tax, total_fees = self.cost_model.calculate_cost(OrderSide.SELL, price, qty)
            trade_val = price * qty
            received_cash = trade_val - total_fees
            new_cash = cash + received_cash

            realized_pnl = (price - position.average_cost) * qty - total_fees

            old_tot = position.quantity
            new_tot = old_tot - qty
            new_avail = position.available_quantity - qty

            order.status = OrderStatus.FILLED
            order.filled_quantity = qty
            order.filled_price = price

            if new_tot <= 0:
                new_pos = None
            else:
                new_pos = Position(
                    symbol=code,
                    quantity=new_tot,
                    available_quantity=new_avail,
                    average_cost=position.average_cost,
                    market_price=price,
                    name=position.name
                )

            return order, new_cash, new_pos, realized_pnl

        order.status = OrderStatus.REJECTED
        return order, cash, position, 0.0
