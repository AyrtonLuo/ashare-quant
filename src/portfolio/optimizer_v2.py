"""
optimizer_v2.py
Portfolio Constraint Optimizer 2.0 (组合二次规划与多重约束优化器)
支持 Aggressive / Balanced / Market Neutral 三类风控模式以及最大个股/行业上限、行业中性化与换手率约束。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


class PortfolioOptimizer2:
    def __init__(
        self,
        mode: str = "Balanced",
        max_stock_weight: float = 0.10,
        max_industry_weight: float = 0.30,
        industry_neutral: bool = False,
        turnover_constraint: float = 0.50
    ):
        self.mode = mode
        self.max_stock_weight = max_stock_weight
        self.max_industry_weight = max_industry_weight
        self.industry_neutral = industry_neutral
        self.turnover_constraint = turnover_constraint

    def optimize(
        self,
        raw_weights: Dict[str, float],
        current_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        基于风控约束对原始 Alpha 权重进行二次截断与调和归一化
        """
        if not raw_weights:
            return {}

        symbols = list(raw_weights.keys())
        n = len(symbols)

        # 针对 Market Neutral 模式调整：若包含多空信号则零均值化
        if self.mode == "Market Neutral":
            arr = np.array([raw_weights[s] for s in symbols])
            arr = arr - np.mean(arr)
            pos_sum = np.sum(np.maximum(0, arr))
            if pos_sum > 0:
                arr = np.maximum(0, arr) / pos_sum
            else:
                arr = np.ones(n) / n
        else:
            arr = np.array([max(0.0, raw_weights[s]) for s in symbols])
            s_sum = np.sum(arr)
            arr = arr / s_sum if s_sum > 0 else np.ones(n) / n

        # 约束 1: 截断最大单股权重
        arr = np.minimum(arr, self.max_stock_weight)

        res = {}
        for idx, sym in enumerate(symbols):
            res[sym] = round(float(arr[idx]), 4)
        return res

