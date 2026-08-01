"""
multi_factor_strategy.py
多因子 Composite Alpha 组合构建策略 (MultiFactorStrategy)
继承 Strategy 抽象基类，集成 FactorEngine、Winsorization、Standardization、Neutralization 与 PortfolioOptimizer。
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from src.strategy.interface import Strategy
from src.strategy.signal import StrategySignal
from src.factors.base import Factor
from src.factors.momentum import MomentumFactor
from src.factors.value import ValueFactor
from src.factors.quality import QualityFactor
from src.factors.volatility import VolatilityFactor
from src.factors.liquidity import LiquidityFactor
from src.factors.engine import FactorEngine
from src.data.provider import MarketDataProvider


class MultiFactorStrategy(Strategy):
    def __init__(
        self,
        symbols: List[str],
        factors: Optional[List[Factor]] = None,
        factor_weights: Optional[Dict[str, float]] = None,
        neutralize: bool = False,
        top_k: int = 3
    ):
        super().__init__(strategy_id="MultiFactor_Alpha_v2")
        self.symbols = symbols
        self.factors = factors or [
            MomentumFactor(20),
            ValueFactor(),
            QualityFactor(),
            VolatilityFactor(20),
            LiquidityFactor(20)
        ]
        self.factor_weights = factor_weights or {
            "Momentum_20D": 0.30,
            "Value_EP": 0.25,
            "Quality_ROE": 0.20,
            "LowVol_20D": 0.15,
            "Liquidity_20D": 0.10
        }
        self.neutralize = neutralize
        self.top_k = top_k

    def generate_signal(
        self,
        data_provider: MarketDataProvider,
        portfolio_state: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> StrategySignal:
        ts = timestamp or pd.Timestamp.now().strftime("%Y-%m-%d")
        engine = FactorEngine(data_provider)

        # 1. 计算多因子横截面矩阵
        f_matrix = engine.compute_factor_matrix(
            symbols=self.symbols,
            factors=self.factors,
            cutoff_date=ts,
            winsorize=True,
            standardize=True,
            neutralize=self.neutralize
        )

        # 2. 合成 Composite Alpha 得分
        composite_scores = engine.combine_composite_alpha(f_matrix, self.factor_weights)
        scores_dict = composite_scores.to_dict()

        # 3. 选出 Top K 高 Alpha 标的并计算目标权重
        sorted_symbols = sorted(scores_dict.keys(), key=lambda s: scores_dict[s], reverse=True)
        selected = sorted_symbols[:min(self.top_k, len(sorted_symbols))]

        target_weights = {}
        if selected:
            top_scores = np.array([scores_dict[s] for s in selected])
            exp_scores = np.exp(top_scores - np.max(top_scores))
            weights = exp_scores / np.sum(exp_scores)
            for sym, w in zip(selected, weights):
                target_weights[sym] = round(float(w), 4)

        return StrategySignal(
            timestamp=ts,
            strategy_id=self.strategy_id,
            symbols=self.symbols,
            target_weights=target_weights,
            scores={s: float(v) for s, v in scores_dict.items()},
            metadata={
                "factor_weights": self.factor_weights,
                "neutralize": self.neutralize,
                "top_k": self.top_k
            }
        )
