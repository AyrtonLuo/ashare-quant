"""
linear.py
线性模型实现 (LinearRegressionModel & RidgeModel)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from sklearn.linear_model import Ridge
from src.ml.models.base import MLModel


class LinearModel(MLModel):
    def __init__(self, alpha: float = 1.0):
        super().__init__(model_name="Linear_Ridge")
        self.model = Ridge(alpha=alpha)
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
        coefs = np.abs(self.model.coef_)
        tot = sum(coefs) if sum(coefs) > 0 else 1.0
        return {f: float(c / tot) for f, c in zip(self.feature_names, coefs)}
