"""
risk_engine.py
A 股大盘风险与动态资金与现金管理分配引擎 (Dynamic Capital Allocator & Market Regime Engine)
1. 判断 A 股特有风控状态 (强势多头 🟢 / 震荡盘整 🟡 / 冰点破位 🔴)
2. 算动态现金保留比例与股票持仓仓位上限 (Equity Cap vs Cash Reserve)
3. 单股风控上限约束 (<= 15%-20%) 与 100 股向下取整
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("risk_engine")


class DynamicCapitalAllocator:
    """
    A 股大盘动态资金与现金分配器
    """
    def __init__(self, index_price: float = 3200.0, index_ma20: float = 3150.0, market_volume_yi: float = 8500.0):
        self.index_price = float(index_price)
        self.index_ma20 = float(index_ma20)
        self.market_volume_yi = float(market_volume_yi)

    def evaluate_market_regime(self) -> Dict[str, Any]:
        """
        评估大盘风控状态：
        • 🟢 强势多头 (指数 > MA20 且 两市成交 > 8000 亿): 允许最高持仓 75%，保留 25% 现金。
        • 🟡 震荡盘整 (指数 >= MA20*0.99 且 6000 亿 <= 两市成交 <= 8000 亿): 强制持仓上限 45%，保留 55% 现金。
        • 🔴 冰点/破位 (指数 < MA20 或 两市成交 < 6000 亿): 强制防守模式，持仓上限 25%，保留 75% 现金避险。
        """
        is_above_ma20 = self.index_price >= self.index_ma20
        vol = self.market_volume_yi

        if is_above_ma20 and vol >= 8000.0:
            regime = "🟢 强势多头"
            color = "#00E676"
            equity_cap_pct = 75.0
            cash_reserve_pct = 25.0
            advice = "市场量价齐升，允许 75% 仓位积极看多，保留 25% 现金应对轮动。"
        elif self.index_price >= (self.index_ma20 * 0.99) and vol >= 6000.0:
            regime = "🟡 震荡盘整"
            color = "#FFD54F"
            equity_cap_pct = 45.0
            cash_reserve_pct = 55.0
            advice = "市场进入缩量盘整阶段，强制压缩持仓上限至 45%，保留 55% 避险现金。"
        else:
            regime = "🔴 冰点防守"
            color = "#FF3333"
            equity_cap_pct = 25.0
            cash_reserve_pct = 75.0
            advice = "大盘指数破位或两市成交低于 6000 亿，开启极客防守模式，保留 75% 现金控风险！"

        return {
            "regime": regime,
            "color": color,
            "equity_cap_pct": equity_cap_pct,
            "cash_reserve_pct": cash_reserve_pct,
            "max_single_stock_pct": 15.0,
            "advice": advice,
            "index_price": round(self.index_price, 2),
            "index_ma20": round(self.index_ma20, 2),
            "market_volume_yi": round(self.market_volume_yi, 1)
        }
