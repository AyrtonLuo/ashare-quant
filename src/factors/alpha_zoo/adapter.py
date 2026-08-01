"""
adapter.py
Alpha 因子适配器 (AlphaFactorAdapter)：
1. 连接 AlphaRegistry 原始 Alpha 计算与 FactorEngine/Neutralizer 因子后处理管道。
2. 提供 Winsorization (去极值)、Z-Score 标准化与中性化处理 (Neutralization)。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from src.factors.alpha_zoo.registry import AlphaRegistry
from src.factors.factor_neutralizer import neutralize_factor


class AlphaFactorAdapter:
    """Alpha 因子后处理与管道适配器"""

    @classmethod
    def compute_raw_alpha(cls, alpha_id: str, df: pd.DataFrame) -> pd.Series:
        """从 AlphaRegistry 获取元数据并计算原始 Alpha"""
        return AlphaRegistry.compute(alpha_id, df)

    @classmethod
    def process_alpha_pipeline(
        cls,
        alpha_id: str,
        df: pd.DataFrame,
        winsorize: bool = True,
        zscore: bool = True,
        neutralize: bool = False,
        industry_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        完整 Alpha 因子处理管道：
        Raw Market Data -> Raw Alpha -> Winsorize -> Z-Score -> Industry Neutralize -> Processed Alpha
        """
        res_df = df.copy()
        raw_alpha = cls.compute_raw_alpha(alpha_id, res_df)
        res_df[f"raw_{alpha_id}"] = raw_alpha

        processed = raw_alpha.copy()

        # Step 1: 3-Sigma / MAD Winsorization
        if winsorize:
            med = processed.median()
            mad = (processed - med).abs().median()
            up = med + 3.0 * 1.4826 * mad
            low = med - 3.0 * 1.4826 * mad
            processed = processed.clip(lower=low, upper=up)

        # Step 2: Z-Score Normalization
        if zscore:
            std = processed.std()
            if std > 1e-8:
                processed = (processed - processed.mean()) / std
            else:
                processed = processed - processed.mean()

        # Step 3: Industry / Cap Neutralization (If requested)
        if neutralize and industry_col and industry_col in res_df.columns:
            res_df[f"factor_tmp"] = processed
            res_df = neutralize_factor(res_df, f"factor_tmp", industry_col)
            processed = res_df[f"factor_tmp_neutralized"] if f"factor_tmp_neutralized" in res_df.columns else res_df[f"factor_tmp"]
            res_df.drop(columns=["factor_tmp", "factor_tmp_neutralized"], errors="ignore", inplace=True)

        res_df[alpha_id] = processed
        return res_df

