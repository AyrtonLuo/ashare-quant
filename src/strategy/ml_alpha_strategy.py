"""
ml_alpha_strategy.py
基于机器学习预测的 ML Alpha 策略 (MLAlphaStrategy)
继承 Strategy 抽象基类。提取实时 Feature Matrix X，调取训练好的 MLModel 预测 Forward Return，按 Top-K 选股生成 StrategySignal。
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from src.strategy.interface import Strategy
from src.strategy.signal import StrategySignal
from src.ml.models.base import MLModel
from src.ml.features import FeatureExtractor
from src.data.provider import MarketDataProvider


class MLAlphaStrategy(Strategy):
    def __init__(self, symbols: List[str], model: MLModel, top_k: int = 3):
        super().__init__(strategy_id=f"ML_Alpha_{model.model_name}")
        self.symbols = symbols
        self.model = model
        self.top_k = top_k

    def generate_signal(
        self,
        data_provider: MarketDataProvider,
        portfolio_state: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> StrategySignal:
        ts = timestamp or pd.Timestamp.now().strftime("%Y-%m-%d")
        extractor = FeatureExtractor(data_provider)
        f_matrix = extractor.extract_features_on_date(self.symbols, cutoff_date=ts)

        scores_dict = {}
        if not f_matrix.empty and self.model.is_fitted:
            preds = self.model.predict(f_matrix)
            scores_dict = preds.to_dict()
        else:
            scores_dict = {s: 0.0 for s in self.symbols}

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
            metadata={"model_name": self.model.model_name, "top_k": self.top_k}
        )
