"""
research_service.py
因子研究与多因子策略服务层 (ResearchService)
隔离底层 FactorEngine 与 Strategy 模块，向 UI 层提供极简接口。
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.provider import MarketDataProvider
from src.factors.momentum import MomentumFactor
from src.factors.value import ValueFactor
from src.factors.quality import QualityFactor
from src.factors.volatility import VolatilityFactor
from src.factors.liquidity import LiquidityFactor
from src.factors.engine import FactorEngine
from src.strategy.multi_factor_strategy import MultiFactorStrategy


class ResearchService:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.factor_engine = FactorEngine(data_provider)

    def run_factor_analysis(
        self,
        symbols: List[str],
        cutoff_date: Optional[str] = None,
        neutralize: bool = False
    ) -> pd.DataFrame:
        factors = [
            MomentumFactor(20),
            ValueFactor(),
            QualityFactor(),
            VolatilityFactor(20),
            LiquidityFactor(20)
        ]
        return self.factor_engine.compute_factor_matrix(
            symbols=symbols,
            factors=factors,
            cutoff_date=cutoff_date,
            winsorize=True,
            standardize=True,
            neutralize=neutralize
        )

    def create_multi_factor_strategy(
        self,
        symbols: List[str],
        factor_weights: Optional[Dict[str, float]] = None,
        neutralize: bool = False,
        top_k: int = 3
    ) -> MultiFactorStrategy:
        return MultiFactorStrategy(
            symbols=symbols,
            factor_weights=factor_weights,
            neutralize=neutralize,
            top_k=top_k
        )
