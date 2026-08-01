"""
paper_trader.py
A 股严格 T+1 模拟盘自动化交易与动态资金调仓引擎 (A-Share T+1 Paper Trader)
1. T+1 持仓规则支持：支持 usable_shares (可卖股份) 与 frozen_shares (今日买入冻结股份)。
2. A 股交易费用算子：买入收取 0.025% 佣金，卖出收取 0.025% 佣金 + 0.05% 印花税。
3. 动态资金分配器 (DynamicCapitalAllocator) 联动：根据大盘风控状态自动留存现金 (25% - 75%)。
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from src.strategy.risk_engine import DynamicCapitalAllocator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("paper_trader")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
PAPER_ACCOUNT_FILE = os.path.join(DATA_DIR, "paper_account.json")


class PaperAccount:
    """
    A 股 T+1 模拟盘账户类
    """
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions = {}  # {symbol: {"name": str, "usable_shares": int, "frozen_shares": int, "shares": int, "cost_price": float}}
        self.trade_logs = []
        self.last_trade_date = ""
        self.load_from_file()

    def reset_account(self, capital: float = 1000000.0):
        """重置账户资金与持仓"""
        self.initial_capital = float(capital)
        self.cash = float(capital)
        self.positions = {}
        self.trade_logs = []
        self.last_trade_date = ""
        self.save_to_file()

    def load_from_file(self):
        """从本地 JSON 读取账户状态并补齐 T+1 字段"""
        if os.path.exists(PAPER_ACCOUNT_FILE):
            try:
                with open(PAPER_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.initial_capital = float(data.get("initial_capital", 1000000.0))
                    self.cash = float(data.get("cash", 1000000.0))
                    raw_pos = data.get("positions", {})
                    
                    self.positions = {}
                    for sym, pos in raw_pos.items():
                        tot_shares = int(pos.get("shares", 0))
                        usable = int(pos.get("usable_shares", tot_shares))
                        frozen = int(pos.get("frozen_shares", 0))
                        self.positions[sym] = {
                            "name": pos.get("name", sym),
                            "shares": tot_shares,
                            "usable_shares": usable,
                            "frozen_shares": frozen,
                            "cost_price": float(pos.get("cost_price", 10.0))
                        }
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
        """跨日自动将今日买入的 T+1 冻结股份 (frozen_shares) 转为可卖股份 (usable_shares)"""
        today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        if self.last_trade_date != today_str:
            for sym, pos in self.positions.items():
                pos['usable_shares'] = pos['shares']
                pos['frozen_shares'] = 0
            self.last_trade_date = today_str
            self.save_to_file()

    def get_summary(self, price_dict: Dict[str, float] = None) -> Dict[str, Any]:
        """
        获取当前模拟账户摘要 (考虑 T+1 可用/冻结股份与浮动盈亏)
        """
        self.unfreeze_t1_shares()
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

            usable = int(pos.get("usable_shares", shares))
            frozen = int(pos.get("frozen_shares", 0))

            pos_list.append({
                "股票代码": sym,
                "股票名称": pos.get("name", sym),
                "总持股数": shares,
                "可卖股份 (T+1)": usable,
                "今日买入冻结": frozen,
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

    def rebalance(self, target_portfolio: pd.DataFrame, market_regime_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        动态现金比率 + A 股 T+1 严格调仓算子：
        - 遵守 T+1 卖出限制：仅可卖出 usable_shares
        - 遵守印花税 (卖出 0.05%) 与佣金 (买卖 0.025%)
        - 遵守 DynamicCapitalAllocator 现金保留门槛
        """
        self.unfreeze_t1_shares()
        if target_portfolio is None or target_portfolio.empty:
            return {"status": "empty_target", "executed_orders": []}

        price_dict = {}
        for _, row in target_portfolio.iterrows():
            sym = str(row['symbol']).zfill(6)
            price_dict[sym] = float(row.get('close', 10.0))

        summary = self.get_summary(price_dict)
        total_equity = summary['total_equity']
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        # 计算有效股票可投总仓位 (扣除动态风控要求的保留现金)
        equity_cap_pct = 75.0
        if market_regime_info:
            equity_cap_pct = float(market_regime_info.get("equity_cap_pct", 75.0))
            
        allowed_equity_capital = total_equity * (equity_cap_pct / 100.0)
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

        # 2. 先处理卖出（受限于 usable_shares T+1 规避限制）
        current_syms = list(self.positions.keys())
        for sym in current_syms:
            pos = self.positions[sym]
            usable_shares = pos.get('usable_shares', pos.get('shares', 0))
            tot_shares = pos.get('shares', 0)
            if tot_shares <= 0:
                continue

            name = pos.get('name', sym)
            p = price_dict.get(sym, pos.get('cost_price', 10.0))
            
            target_w = target_dict.get(sym, 0.0)
            target_amt = allowed_equity_capital * target_w
            target_hands = int(target_amt // (p * 100))
            target_shares = target_hands * 100

            if target_shares < tot_shares:
                needed_sell = tot_shares - target_shares
                actual_sell = min(needed_sell, usable_shares)
                
                # 100 股向下取整
                actual_sell = (actual_sell // 100) * 100
                
                if actual_sell > 0:
                    amount = actual_sell * p
                    comm_fee = amount * 0.00025  # 0.025% 佣金
                    stamp_tax = amount * 0.0005  # 0.05% 印花税
                    total_fee = comm_fee + stamp_tax
                    net_amount = amount - total_fee

                    self.cash += net_amount
                    new_tot = tot_shares - actual_sell
                    new_usable = usable_shares - actual_sell
                    
                    if new_tot <= 0:
                        del self.positions[sym]
                    else:
                        self.positions[sym]['shares'] = new_tot
                        self.positions[sym]['usable_shares'] = new_usable

                    order = {
                        "成交时间": now_str,
                        "交易动作": "SELL 卖出 (T+1解冻股)",
                        "股票代码": sym,
                        "股票名称": name,
                        "成交价格": round(p, 2),
                        "成交股数": actual_sell,
                        "成交金额": round(amount, 2),
                        "印花税+佣金": round(total_fee, 2)
                    }
                    self.trade_logs.insert(0, order)
                    executed_orders.append(order)

        # 3. 再处理买入（受限于可用现金与 100 股一手）
        for sym, target_w in target_dict.items():
            name = target_name_dict.get(sym, sym)
            p = price_dict.get(sym, 10.0)
            if p <= 0:
                continue

            curr_shares = self.positions.get(sym, {}).get('shares', 0)
            target_amt = allowed_equity_capital * target_w
            target_hands = int(target_amt // (p * 100))
            target_shares = target_hands * 100

            if target_shares > curr_shares:
                buy_shares = target_shares - curr_shares
                amount = buy_shares * p
                comm_fee = amount * 0.00025  # 0.025% 佣金
                total_cost = amount + comm_fee

                if self.cash >= total_cost and buy_shares >= 100:
                    self.cash -= total_cost
                    if sym not in self.positions:
                        self.positions[sym] = {
                            "name": name,
                            "shares": buy_shares,
                            "usable_shares": 0,
                            "frozen_shares": buy_shares,
                            "cost_price": p
                        }
                    else:
                        old_shares = self.positions[sym]['shares']
                        old_cost = self.positions[sym]['cost_price']
                        new_shares = old_shares + buy_shares
                        new_cost = (old_shares * old_cost + amount) / new_shares
                        
                        self.positions[sym]['shares'] = new_shares
                        self.positions[sym]['frozen_shares'] += buy_shares
                        self.positions[sym]['cost_price'] = round(new_cost, 2)

                    order = {
                        "成交时间": now_str,
                        "交易动作": "BUY 买入 (T+1当日冻结)",
                        "股票代码": sym,
                        "股票名称": name,
                        "成交价格": round(p, 2),
                        "成交股数": buy_shares,
                        "成交金额": round(amount, 2),
                        "印花税+佣金": round(comm_fee, 2)
                    }
                    self.trade_logs.insert(0, order)
                    executed_orders.append(order)

        self.save_to_file()
        return {"status": "success", "executed_orders": executed_orders}
