"""
paper_trader.py
模拟盘自动化交易与调仓控制台引擎 (Paper Trading & Automated Rebalancing Engine)
1. 模拟账户数据结构 (PaperAccount): 持久化存储现金、初始资金、持仓、成交日志
2. 自动化调仓算子 (rebalance_portfolio): 自动对比目标权重与当前持仓，计算买卖差额并模拟撮合
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("paper_trader")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
PAPER_ACCOUNT_FILE = os.path.join(DATA_DIR, "paper_account.json")


class PaperAccount:
    """
    模拟盘账户类 (PaperAccount)
    支持持久化存储至 data/paper_account.json
    """
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions = {}  # {symbol: {"name": str, "shares": int, "cost_price": float}}
        self.trade_logs = []  # [{"time": str, "action": "BUY"/"SELL", "symbol": str, "name": str, "price": float, "shares": int, "amount": float, "fee": float}]
        self.load_from_file()

    def reset_account(self, capital: float = 1000000.0):
        """重置账户资金与持仓"""
        self.initial_capital = float(capital)
        self.cash = float(capital)
        self.positions = {}
        self.trade_logs = []
        self.save_to_file()

    def load_from_file(self):
        """从本地 JSON 文件读取账户状态"""
        if os.path.exists(PAPER_ACCOUNT_FILE):
            try:
                with open(PAPER_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.initial_capital = float(data.get("initial_capital", 1000000.0))
                    self.cash = float(data.get("cash", 1000000.0))
                    self.positions = data.get("positions", {})
                    self.trade_logs = data.get("trade_logs", [])
            except Exception as e:
                logger.warning(f"读取 paper_account.json 失败 ({e})，使用初始化默认值...")

    def save_to_file(self):
        """将账户状态持久化保存至 JSON 文件"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PAPER_ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "initial_capital": self.initial_capital,
                    "cash": self.cash,
                    "positions": self.positions,
                    "trade_logs": self.trade_logs
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 paper_account.json 失败 ({e})")

    def get_summary(self, price_dict: Dict[str, float] = None) -> Dict[str, Any]:
        """
        获取当前模拟账户摘要（总资产、持仓市值、累计收益率）
        """
        price_dict = price_dict or {}
        market_value = 0.0
        pos_list = []

        for sym, pos in self.positions.items():
            shares = int(pos.get("shares", 0))
            if shares <= 0:
                continue
            cost_p = float(pos.get("cost_price", 10.0))
            latest_p = float(price_dict.get(sym, cost_p))
            val = shares * latest_p
            market_value += val
            pnl_pct = ((latest_p - cost_p) / cost_p * 100.0) if cost_p > 0 else 0.0

            pos_list.append({
                "股票代码": sym,
                "股票名称": pos.get("name", sym),
                "持股数量": shares,
                "持仓成本价": round(cost_p, 2),
                "最新价": round(latest_p, 2),
                "持仓市值": round(val, 2),
                "浮动盈亏 %": round(pnl_pct, 2)
            })

        total_equity = self.cash + market_value
        pnl_pct = ((total_equity - self.initial_capital) / self.initial_capital * 100.0) if self.initial_capital > 0 else 0.0

        return {
            "initial_capital": self.initial_capital,
            "cash": round(self.cash, 2),
            "market_value": round(market_value, 2),
            "total_equity": round(total_equity, 2),
            "pnl_pct": round(pnl_pct, 2),
            "positions_df": pd.DataFrame(pos_list) if pos_list else pd.DataFrame(),
            "trade_logs_df": pd.DataFrame(self.trade_logs) if self.trade_logs else pd.DataFrame()
        }

    def rebalance(self, target_portfolio: pd.DataFrame, fee_rate: float = 0.0003) -> Dict[str, Any]:
        """
        根据目标持仓 DataFrame (包含 symbol, name, close, target_weight/Markowitz 建议权重 %)
        自动比对当前持仓，生成买卖订单并撮合调仓
        """
        if target_portfolio is None or target_portfolio.empty:
            return {"status": "empty_target", "executed_orders": []}

        # 估算当前可用总资产
        price_dict = {}
        for _, row in target_portfolio.iterrows():
            sym = str(row['symbol']).zfill(6)
            price_dict[sym] = float(row.get('close', 10.0))

        summary = self.get_summary(price_dict)
        total_equity = summary['total_equity']
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        executed_orders = []

        # 1. 目标权重字典
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

        # 2. 先处理卖出（超配或不在目标池中的标的）
        current_syms = list(self.positions.keys())
        for sym in current_syms:
            pos = self.positions[sym]
            curr_shares = pos.get('shares', 0)
            if curr_shares <= 0:
                continue
            name = pos.get('name', sym)
            p = price_dict.get(sym, pos.get('cost_price', 10.0))
            
            target_w = target_dict.get(sym, 0.0)
            target_amt = total_equity * target_w
            target_hands = int(target_amt // (p * 100))
            target_shares = target_hands * 100

            if target_shares < curr_shares:
                sell_shares = curr_shares - target_shares
                amount = sell_shares * p
                fee = amount * fee_rate
                net_amount = amount - fee

                self.cash += net_amount
                if target_shares == 0:
                    del self.positions[sym]
                else:
                    self.positions[sym]['shares'] = target_shares

                order = {
                    "成交时间": now_str,
                    "交易动作": "SELL 卖出",
                    "股票代码": sym,
                    "股票名称": name,
                    "成交价格": round(p, 2),
                    "成交股数": sell_shares,
                    "成交金额": round(amount, 2),
                    "手续费": round(fee, 2)
                }
                self.trade_logs.insert(0, order)
                executed_orders.append(order)

        # 3. 再处理买入（欠配标的）
        for sym, target_w in target_dict.items():
            name = target_name_dict.get(sym, sym)
            p = price_dict.get(sym, 10.0)
            if p <= 0:
                continue

            curr_shares = self.positions.get(sym, {}).get('shares', 0)
            target_amt = total_equity * target_w
            target_hands = int(target_amt // (p * 100))
            target_shares = target_hands * 100

            if target_shares > curr_shares:
                buy_shares = target_shares - curr_shares
                amount = buy_shares * p
                fee = amount * fee_rate
                total_cost = amount + fee

                if self.cash >= total_cost and buy_shares >= 100:
                    self.cash -= total_cost
                    if sym not in self.positions:
                        self.positions[sym] = {"name": name, "shares": buy_shares, "cost_price": p}
                    else:
                        old_shares = self.positions[sym]['shares']
                        old_cost = self.positions[sym]['cost_price']
                        new_shares = old_shares + buy_shares
                        new_cost = (old_shares * old_cost + amount) / new_shares
                        self.positions[sym]['shares'] = new_shares
                        self.positions[sym]['cost_price'] = round(new_cost, 2)

                    order = {
                        "成交时间": now_str,
                        "交易动作": "BUY 买入",
                        "股票代码": sym,
                        "股票名称": name,
                        "成交价格": round(p, 2),
                        "成交股数": buy_shares,
                        "成交金额": round(amount, 2),
                        "手续费": round(fee, 2)
                    }
                    self.trade_logs.insert(0, order)
                    executed_orders.append(order)

        self.save_to_file()
        return {"status": "success", "executed_orders": executed_orders}
