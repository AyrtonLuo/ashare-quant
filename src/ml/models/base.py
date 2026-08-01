"""
base.py
机器学习模型抽象基类 (MLModel)
定义统一的 fit, predict 与 feature_importance 规范
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


class MLModel(ABC):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.is_fitted = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series):
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series:
        pass

    @abstractmethod
    def get_feature_importance(self, feature_names: list) -> Dict[str, float]:
        pass
