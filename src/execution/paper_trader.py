"""
paper_trader.py
A 股严格 T+1 模拟盘自动化交易与动态资金调仓引擎 (A-Share T+1 Paper Trader)
重构为 Portfolio Engine 2.0 门面 (Facade)，保持 100% 现有 API 兼容性。
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from src.strategy.risk_engine import DynamicCapitalAllocator
from src.portfolio.portfolio import Portfolio
from src.portfolio.order import Order, OrderSide, OrderStatus
from src.portfolio.position import Position

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("paper_trader")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
PAPER_ACCOUNT_FILE = os.path.join(DATA_DIR, "paper_account.json")
PRICE_COLUMN_CANDIDATES = ("close", "最新价", "price", "last_price", "成交价格", "参考价")


def _extract_target_price(row: pd.Series, default: float = 10.0) -> float:
    """
    Extract the execution reference price from a target row.
    """
    for col in PRICE_COLUMN_CANDIDATES:
        value = row.get(col, None)
        if value is None or pd.isna(value):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return float(default)


class PaperAccount:
    """
    A 股 T+1 模拟盘账户类 (基于 Portfolio Engine 2.0 的 100% 兼容门面)
    """
    def __init__(self, initial_capital: float = 1000000.0):
        self._portfolio = Portfolio(initial_capital=initial_capital)
        self.load_from_file()

    @property
    def initial_capital(self) -> float:
        return self._portfolio.initial_capital

    @initial_capital.setter
    def initial_capital(self, val: float):
        self._portfolio.accounting.initial_capital = float(val)

    @property
    def cash(self) -> float:
        return self._portfolio.cash

    @cash.setter
    def cash(self, val: float):
        self._portfolio.cash = float(val)

    @property
    def positions(self) -> Dict[str, Dict[str, Any]]:
        res = {}
        for sym, pos in self._portfolio.positions.items():
            res[sym] = {
                "name": pos.name or sym,
                "shares": pos.quantity,
                "usable_shares": pos.available_quantity,
                "frozen_shares": pos.quantity - pos.available_quantity,
                "cost_price": pos.average_cost
            }
        return res

    @positions.setter
    def positions(self, raw_pos: Dict[str, Dict[str, Any]]):
        new_dict = {}
        for sym, pos in raw_pos.items():
            tot = int(pos.get("shares", 0))
            usable = int(pos.get("usable_shares", tot))
            cost = float(pos.get("cost_price", 10.0))
            name = str(pos.get("name", sym))
            new_dict[sym] = Position(
                symbol=sym,
                quantity=tot,
                available_quantity=usable,
                average_cost=cost,
                market_price=cost,
                name=name
            )
        self._portfolio.positions = new_dict

    @property
    def trade_logs(self) -> List[Dict[str, Any]]:
        return [o.to_dict() for o in self._portfolio.orders_history]

    @trade_logs.setter
    def trade_logs(self, logs: List[Dict[str, Any]]):
        orders = []
        for l in logs:
            o = Order(
                order_id=l.get("order_id", "000000"),
                symbol=l.get("symbol", "000001"),
                side=OrderSide.BUY if l.get("side") == "BUY" else OrderSide.SELL,
                quantity=int(l.get("quantity", 0)),
                price=float(l.get("price", 10.0)),
                status=OrderStatus.FILLED,
                created_at=l.get("created_at", l.get("timestamp", ""))
            )
            orders.append(o)
        self._portfolio.orders_history = orders

    @property
    def last_trade_date(self) -> str:
        return self._portfolio.last_trade_date

    @last_trade_date.setter
    def last_trade_date(self, val: str):
        self._portfolio.last_trade_date = str(val)

    def reset_account(self, capital: float = 1000000.0):
        """重置账户资金与持仓"""
        self._portfolio = Portfolio(initial_capital=capital)
        self.save_to_file()

    def load_from_file(self):
        """从本地 JSON 读取账户状态并补齐 T+1 字段"""
        if os.path.exists(PAPER_ACCOUNT_FILE):
            try:
                with open(PAPER_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cap = float(data.get("initial_capital", 1000000.0))
                    csh = float(data.get("cash", 1000000.0))
                    self._portfolio = Portfolio(initial_capital=cap)
                    self._portfolio.cash = csh
                    self.positions = data.get("positions", {})
                    self.trade_logs = data.get("trade_logs", [])
                    self.last_trade_date = data.get("last_trade_date", "")
            except Exception as e:
                logger.warning(f"读取 paper_account.json 异常 ({e})...")

    def save_to_file(self):
        """持久化保存账户状态"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PAPER_ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "initial_capital": self.initial_capital,
                    "cash": self.cash,
                    "positions": self.positions,
                    "trade_logs": self.trade_logs,
                    "last_trade_date": self.last_trade_date
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 paper_account.json 失败 ({e})")

    def unfreeze_t1_shares(self):
        """跨日自动转 T+1 可卖股份"""
        self._portfolio.unfreeze_t1()

    def get_summary(self, price_dict: Dict[str, float] = None) -> Dict[str, Any]:
        """
        获取账户摘要 (完全兼容旧端与旧测试)
        """
        price_dict = price_dict or {}
        summary = self._portfolio.get_summary(price_dict)

        pos_list = []
        for sym, pos in self._portfolio.positions.items():
            shares = pos.quantity
            if shares <= 0:
                continue
            cost_p = pos.average_cost
            latest_p = price_dict.get(sym, cost_p)
            val = shares * latest_p
            pnl_pct = ((latest_p - cost_p) / cost_p * 100.0) if cost_p > 0 else 0.0

            pos_list.append({
                "股票代码": sym,
                "股票名称": pos.name or sym,
                "总持股数": shares,
                "可卖股份 (T+1)": pos.available_quantity,
                "今日买入冻结": shares - pos.available_quantity,
                "持仓成本价": round(cost_p, 2),
                "最新价": round(latest_p, 2),
                "持仓市值": round(val, 2),
                "浮动盈亏 %": round(pnl_pct, 2)
            })

        return {
            "initial_capital": summary["initial_capital"],
            "cash": summary["cash"],
            "market_value": summary["market_value"],
            "total_equity": summary["equity"],
            "pnl_pct": summary["pnl_pct"],
            "total_return_pct": summary.get("total_return_pct", summary["pnl_pct"]),
            "positions_df": pd.DataFrame(pos_list) if pos_list else pd.DataFrame(columns=[
                "股票代码", "股票名称", "总持股数", "可卖股份 (T+1)", "今日买入冻结", "持仓成本价", "最新价", "持仓市值", "浮动盈亏 %"
            ]),
            "trade_logs_df": pd.DataFrame(self.trade_logs) if self.trade_logs else pd.DataFrame()
        }


    def rebalance(self, target_portfolio: pd.DataFrame, market_regime_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调仓逻辑：通过 Portfolio Engine 2.0 统一 Order -> Execution Engine 进行调仓
        """
        self.unfreeze_t1_shares()
        if target_portfolio is None or target_portfolio.empty:
            return {"status": "empty_target", "executed_orders": []}

        price_dict = {}
        for _, row in target_portfolio.iterrows():
            sym = str(row['symbol']).zfill(6)
            price_dict[sym] = _extract_target_price(row)

        summary = self.get_summary(price_dict)
        total_equity = summary['total_equity']

        equity_cap_pct = 75.0
        if market_regime_info:
            equity_cap_pct = float(market_regime_info.get("equity_cap_pct", 75.0))

        allowed_capital = total_equity * (equity_cap_pct / 100.0)
        executed_orders = []

        target_dict = {}
        target_name_dict = {}
        for _, row in target_portfolio.iterrows():
            sym = str(row['symbol']).zfill(6)
            name = str(row.get('name', sym))
            target_name_dict[sym] = name
            w = float(row.get('target_weight', row.get('Markowitz 建议权重 %', 0.0)))
            if w > 1.0:
                w = w / 100.0
            target_dict[sym] = w

        # 1. 先卖出调仓
        for sym in list(self._portfolio.positions.keys()):
            pos = self._portfolio.positions[sym]
            usable_shares = pos.available_quantity
            if pos.quantity <= 0:
                continue

            p = price_dict.get(sym, pos.average_cost)
            target_w = target_dict.get(sym, 0.0)
            target_val = allowed_capital * target_w
            target_shares = int((target_val // (p * 100)) * 100) if p > 0 else 0

            if pos.quantity > target_shares:
                sell_req = pos.quantity - target_shares
                actual_sell = min(sell_req, usable_shares)
                actual_sell = (actual_sell // 100) * 100
                if actual_sell > 0:
                    order = Order(symbol=sym, side=OrderSide.SELL, quantity=actual_sell, price=p)
                    exec_order = self._portfolio.submit_order(order)
                    if exec_order.status == OrderStatus.FILLED:
                        executed_orders.append(exec_order.to_dict())

        # 2. 再买入调仓
        for sym, target_w in target_dict.items():
            if target_w <= 0:
                continue
            p = price_dict.get(sym, 10.0)
            target_val = allowed_capital * target_w
            target_shares = int((target_val // (p * 100)) * 100) if p > 0 else 0

            curr_pos = self._portfolio.positions.get(sym, None)
            curr_shares = curr_pos.quantity if curr_pos else 0

            if target_shares > curr_shares:
                buy_req = target_shares - curr_shares
                buy_req = (buy_req // 100) * 100
                if buy_req > 0:
                    order = Order(symbol=sym, side=OrderSide.BUY, quantity=buy_req, price=p)
                    exec_order = self._portfolio.submit_order(order)
                    if exec_order.status == OrderStatus.FILLED:
                        executed_orders.append(exec_order.to_dict())

        if executed_orders:
            self.save_to_file()

        return {
            "status": "success",
            "executed_orders": executed_orders,
            "account_summary": self.get_summary(price_dict)
        }
