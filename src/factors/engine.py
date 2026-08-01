"""
engine.py
统一因子引擎 (FactorEngine)
负责因子批处理计算、MAD 3倍去极值 (Winsorization)、Z-Score 标准化 (Standardization)、行业/市值中性化 (Neutralization) 与复合 Alpha 合成 (CompositeAlpha)。
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from src.factors.base import Factor
from src.data.provider import MarketDataProvider
from src.strategy.factor_neutralizer import neutralize_factor

logger = logging.getLogger("factor_engine")


def mad_winsorize(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """MAD 3倍去极值"""
    s = series.copy()
    median = s.median()
    mad = (s - median).abs().median()
    if mad == 0:
        return s
    upper = median + n_mad * 1.4826 * mad
    lower = median - n_mad * 1.4826 * mad
    return s.clip(lower=lower, upper=upper)


def zscore_standardize(series: pd.Series) -> pd.Series:
    """Z-Score 标准化"""
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


class FactorEngine:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider

    def compute_factor_matrix(
        self,
        symbols: List[str],
        factors: List[Factor],
        cutoff_date: Optional[str] = None,
        winsorize: bool = True,
        standardize: bool = True,
        neutralize: bool = False
    ) -> pd.DataFrame:
        """
        计算多因子横截面矩阵，包含 MAD 去极值、Z-Score 标准化与中性化
        返回: DataFrame (index=symbols, columns=[factor.name])
        """
        raw_dict = {}
        for factor in factors:
            factor_vals = {}
            for sym in symbols:
                try:
                    val = factor.compute(sym, self.data_provider, cutoff_date=cutoff_date)
                    factor_vals[sym] = float(val)
                except Exception as e:
                    logger.warning(f"计算 {sym} 因子 {factor.name} 异常 ({e})")
                    factor_vals[sym] = 0.0

            s = pd.Series(factor_vals)
            if winsorize:
                s = mad_winsorize(s)
            if standardize:
                s = zscore_standardize(s)
            raw_dict[factor.name] = s

        df = pd.DataFrame(raw_dict, index=symbols)

        if neutralize and not df.empty:
            try:
                for col in df.columns:
                    sec_df = pd.DataFrame({"symbol": symbols, "score": df[col]})
                    neut_df = neutralize_factor(sec_df, score_col="score")
                    if "neutralized_score" in neut_df.columns:
                        df[col] = neut_df["neutralized_score"].values
            except Exception as e:
                logger.warning(f"因子中性化处理异常 ({e})，保留原始得分")

        return df

    def combine_composite_alpha(
        self,
        factor_matrix: pd.DataFrame,
        factor_weights: Dict[str, float]
    ) -> pd.Series:
        """
        根据因子权重进行加权合成得到 Composite Alpha 分值
        """
        if factor_matrix.empty:
            return pd.Series(dtype=float)

        composite = pd.Series(0.0, index=factor_matrix.index)
        tot_w = sum(abs(w) for w in factor_weights.values()) if factor_weights else 1.0
        if tot_w <= 0:
            tot_w = 1.0

        for col, w in factor_weights.items():
            if col in factor_matrix.columns:
                composite += factor_matrix[col] * (w / tot_w)

        return zscore_standardize(composite)
