"""
evaluation.py
机器学习预测能力评估器 (MLEvaluator)
计算 RMSE, MAE, R², IC (Pearson Correlation), Rank IC (Spearman Correlation) 与 ICIR。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from scipy.stats import spearmanr, pearsonr


class MLEvaluator:
    @staticmethod
    def evaluate(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, Any]:
        """
        计算全套预测评估指标
        """
        if len(y_true) == 0 or len(y_pred) == 0 or len(y_true) != len(y_pred):
            return {"RMSE": 0.0, "MAE": 0.0, "R2": 0.0, "IC": 0.0, "RankIC": 0.0, "ICIR": 0.0}

        y_t = y_true.values
        y_p = y_pred.values

        rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
        mae = float(np.mean(np.abs(y_t - y_p)))

        ss_res = np.sum((y_t - y_p) ** 2)
        ss_tot = np.sum((y_t - np.mean(y_t)) ** 2)
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

        ic, _ = pearsonr(y_t, y_p) if (np.std(y_t) > 0 and np.std(y_p) > 0) else (0.0, 0.0)
        rank_ic, _ = spearmanr(y_t, y_p) if (np.std(y_t) > 0 and np.std(y_p) > 0) else (0.0, 0.0)

        ic = float(ic) if not np.isnan(ic) else 0.0
        rank_ic = float(rank_ic) if not np.isnan(rank_ic) else 0.0

        icir = float(ic * np.sqrt(252)) if abs(ic) > 0 else 0.0

        return {
            "RMSE": round(rmse, 6),
            "MAE": round(mae, 6),
            "R2": round(r2, 4),
            "IC": round(ic, 4),
            "RankIC": round(rank_ic, 4),
            "ICIR": round(icir, 2)
        }
