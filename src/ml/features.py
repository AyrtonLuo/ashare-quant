"""
features.py
机器学习特征工程模块 (FeatureExtractor)
将 FactorEngine 的多因子分值 (Momentum 20/60/120D, Value, Quality, Volatility, Liquidity) 提取并构建横截面 Feature Matrix X。
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


class FeatureExtractor:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.factors = [
            MomentumFactor(20),
            MomentumFactor(60),
            MomentumFactor(120),
            ValueFactor(),
            QualityFactor(),
            VolatilityFactor(20),
            VolatilityFactor(60),
            LiquidityFactor(20)
        ]
        self.engine = FactorEngine(data_provider)

    def extract_features_on_date(self, symbols: List[str], cutoff_date: str) -> pd.DataFrame:
        """
        提取指定日期 cutoff_date 的全标的特征矩阵 X
        返回: DataFrame (index=symbols, columns=feature_names)
        """
        f_matrix = self.engine.compute_factor_matrix(
            symbols=symbols,
            factors=self.factors,
            cutoff_date=cutoff_date,
            winsorize=True,
            standardize=True,
            neutralize=False
        )
        return f_matrix
