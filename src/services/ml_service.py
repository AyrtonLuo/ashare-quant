"""
ml_service.py
机器学习 Alpha 服务层 (MLService)
隔离 ML 模型训练、预测与策略封装。
"""

import pandas as pd
from typing import Dict, Any, List, Tuple
from src.data.provider import MarketDataProvider
from src.ml.features import FeatureExtractor
from src.ml.models.linear import LinearModel
from src.ml.models.tree import RandomForestModel, GradientBoostingModel
from src.strategy.ml_alpha_strategy import MLAlphaStrategy


class MLService:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.extractor = FeatureExtractor(data_provider)

    def train_ml_model(
        self,
        symbols: List[str],
        cutoff_date: str,
        model_type: str = "RandomForest"
    ) -> Tuple[Any, pd.DataFrame]:
        train_x = self.extractor.extract_features_on_date(symbols, cutoff_date=cutoff_date)
        train_y = train_x.get("Momentum_20D", pd.Series(0.0, index=train_x.index)) * 0.5 + train_x.get("Value_EP", pd.Series(0.0, index=train_x.index)) * 0.5

        if model_type == "Linear Ridge":
            model = LinearModel()
        elif model_type == "RandomForest":
            model = RandomForestModel(n_estimators=30)
        else:
            model = GradientBoostingModel(max_iter=30)

        model.fit(train_x, train_y)
        return model, train_x

    def create_ml_strategy(self, symbols: List[str], model: Any, top_k: int = 2) -> MLAlphaStrategy:
        return MLAlphaStrategy(symbols=symbols, model=model, top_k=top_k)
