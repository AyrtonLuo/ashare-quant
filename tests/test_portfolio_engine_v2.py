"""
test_portfolio_engine_v2.py
Phase 2B-2G Portfolio Engine 2.0 全套逻辑与 A 股规则单元测试
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.portfolio.position import Position
from src.portfolio.order import Order, OrderSide, OrderStatus
from src.portfolio.execution import ExecutionEngine, TransactionCostModel
from src.portfolio.accounting import PortfolioAccounting
from src.portfolio.portfolio import Portfolio
from src.execution.paper_trader import PaperAccount


def test_position_model():
    pos = Position(symbol="600519", quantity=200, available_quantity=100, average_cost=1000.0, market_price=1200.0)
    assert pos.market_value == 240000.0
    assert pos.unrealized_pnl == 40000.0
    assert pos.unrealized_pnl_pct == 20.0
    d = pos.to_dict()
    assert d["frozen_quantity"] == 100


def test_order_creation_and_fill():
    order = Order(symbol="600519", side=OrderSide.BUY, quantity=100, price=1500.0)
    assert order.status == OrderStatus.PENDING
    assert order.side == OrderSide.BUY

    engine = ExecutionEngine()
    exec_order, new_cash, pos, pnl = engine.validate_and_execute(order, cash=200000.0)
    assert exec_order.status == OrderStatus.FILLED
    assert pos is not None
    assert pos.quantity == 100
    assert pos.available_quantity == 0  # T+1 冻结
    assert new_cash < 200000.0


def test_buy_must_be_100_share_multiple():
    order = Order(symbol="600519", side=OrderSide.BUY, quantity=150, price=100.0)
    engine = ExecutionEngine()
    exec_order, new_cash, pos, pnl = engine.validate_and_execute(order, cash=100000.0)
    assert exec_order.status == OrderStatus.FILLED
    assert exec_order.filled_quantity == 100
    assert pos.quantity == 100


def test_sell_available_quantity_and_t1():
    pos = Position(symbol="600519", quantity=200, available_quantity=100, average_cost=100.0, market_price=120.0)
    order = Order(symbol="600519", side=OrderSide.SELL, quantity=200, price=120.0)
    engine = ExecutionEngine()
    exec_order, new_cash, new_pos, pnl = engine.validate_and_execute(order, cash=50000.0, position=pos)
    assert exec_order.status == OrderStatus.FILLED
    assert exec_order.filled_quantity == 100  # 仅成功卖出可卖的 100 股
    assert new_pos.quantity == 100
    assert pnl > 0  # 卖出获得正实现盈亏


def test_insufficient_cash():
    order = Order(symbol="600519", side=OrderSide.BUY, quantity=10000, price=1000.0)
    engine = ExecutionEngine()
    exec_order, new_cash, pos, pnl = engine.validate_and_execute(order, cash=5000.0)
    assert exec_order.status == OrderStatus.REJECTED
    assert "可用现金不足" in exec_order.reason


def test_limit_up_limit_down_rules():
    engine = ExecutionEngine()
    buy_order = Order(symbol="600519", side=OrderSide.BUY, quantity=100, price=100.0)
    exec_b, _, _, _ = engine.validate_and_execute(buy_order, cash=100000.0, is_limit_up=True)
    assert exec_b.status == OrderStatus.REJECTED
    assert "涨停" in exec_b.reason

    pos = Position(symbol="600519", quantity=100, available_quantity=100, average_cost=100.0, market_price=100.0)
    sell_order = Order(symbol="600519", side=OrderSide.SELL, quantity=100, price=100.0)
    exec_s, _, _, _ = engine.validate_and_execute(sell_order, cash=100000.0, position=pos, is_limit_down=True)
    assert exec_s.status == OrderStatus.REJECTED
    assert "跌停" in exec_s.reason


def test_accounting_conservation():
    accounting = PortfolioAccounting(initial_capital=100000.0, cash=60000.0)
    positions = {
        "600519": Position(symbol="600519", quantity=200, average_cost=200.0, market_price=200.0)
    }
    summary = accounting.calculate(positions, {"600519": 200.0})
    assert summary["cash"] == 60000.0
    assert summary["market_value"] == 40000.0
    assert summary["equity"] == summary["cash"] + summary["market_value"]
    assert summary["equity"] == 100000.0


def test_paper_account_facade(monkeypatch, tmp_path):
    account_file = tmp_path / "paper_account.json"
    import src.execution.paper_trader as pt
    monkeypatch.setattr(pt, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pt, "PAPER_ACCOUNT_FILE", str(account_file))

    acc = PaperAccount(initial_capital=500000.0)
    summary = acc.get_summary({"600519": 100.0})
    assert summary["initial_capital"] == 500000.0
    assert summary["cash"] == 500000.0

    target_df = pd.DataFrame([
        {"symbol": "600519", "name": "贵州茅台", "price": 100.0, "target_weight": 0.20}
    ])
    res = acc.rebalance(target_df)
    assert res["status"] == "success"
    assert len(res["executed_orders"]) == 1
    new_summary = acc.get_summary({"600519": 100.0})
    assert new_summary["market_value"] > 0
    assert new_summary["cash"] < 500000.0
    assert abs(new_summary["cash"] + new_summary["market_value"] - 500000.0) < 50.0
