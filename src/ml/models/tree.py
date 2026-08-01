"""
tree.py
树模型与 Gradient Boosting 模型实现 (RandomForestModel & HistGradientBoostingModel)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from src.ml.models.base import MLModel


class RandomForestModel(MLModel):
    def __init__(self, n_estimators: int = 50, max_depth: int = 5, random_state: int = 42):
        super().__init__(model_name="RandomForest")
        self.model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=random_state)
        self.feature_names = []

    def fit(self, X: pd.DataFrame, y: pd.Series):
        if X.empty:
            return
        self.feature_names = list(X.columns)
        X_clean = X.fillna(0.0)
        y_clean = y.fillna(0.0)
        self.model.fit(X_clean, y_clean)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if not self.is_fitted or X.empty:
            return pd.Series(0.0, index=X.index)
        if self.feature_names:
            X_clean = X.reindex(columns=self.feature_names, fill_value=0.0)
        else:
            X_clean = X.fillna(0.0)
        preds = self.model.predict(X_clean)
        return pd.Series(preds, index=X.index)

    def get_feature_importance(self, feature_names: list) -> Dict[str, float]:
        if not self.is_fitted:
            return {f: 0.0 for f in feature_names}
        importances = self.model.feature_importances_
        tot = sum(importances) if sum(importances) > 0 else 1.0
        return {f: float(imp / tot) for f, imp in zip(self.feature_names, importances)}


class GradientBoostingModel(MLModel):
    def __init__(self, max_iter: int = 50, random_state: int = 42):
        super().__init__(model_name="HistGradientBoosting")
        self.model = HistGradientBoostingRegressor(max_iter=max_iter, random_state=random_state)
        self.feature_names = []

    def fit(self, X: pd.DataFrame, y: pd.Series):
        if X.empty:
            return
        self.feature_names = list(X.columns)
        X_clean = X.fillna(0.0)
        y_clean = y.fillna(0.0)
        self.model.fit(X_clean, y_clean)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if not self.is_fitted or X.empty:
            return pd.Series(0.0, index=X.index)
        if self.feature_names:
            X_clean = X.reindex(columns=self.feature_names, fill_value=0.0)
        else:
            X_clean = X.fillna(0.0)
        preds = self.model.predict(X_clean)
        return pd.Series(preds, index=X.index)

    def get_feature_importance(self, feature_names: list) -> Dict[str, float]:
        if not self.is_fitted or not self.feature_names:
            return {f: 0.0 for f in feature_names}
        eq_imp = 1.0 / len(self.feature_names)
        return {f: eq_imp for f in self.feature_names}
