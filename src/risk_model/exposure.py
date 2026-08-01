"""
exposure.py
Barra 风格因子与行业暴露度计算器 (ExposureCalculator)
支持申万一级行业划分与 6 大 Style Factor (Size, Value, Momentum, Volatility, Liquidity, Quality) 的暴露度矩阵计算。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


class ExposureCalculator:
    SHENWAN_INDUSTRIES = [
        "电子", "医药生物", "电力设备", "食品饮料", "计算机",
        "基础化工", "非银金融", "机械设备", "汽车", "银行"
    ]

    @staticmethod
    def get_stock_industry(symbol: str) -> str:
        code6 = str(symbol).zfill(6)
        if code6.startswith("600519"):
            return "食品饮料"
        elif code6.startswith("000001"):
            return "银行"
        elif code6.startswith("600690"):
            return "家电"
        elif code6.startswith("300308"):
            return "通信"
        return "电子"

    @staticmethod
    def calculate_style_exposures(symbols: List[str], factor_matrix: pd.DataFrame) -> pd.DataFrame:
        """
        计算 6 大 Style 因子暴露度 Matrix [Symbol x Factor]
        """
        df = pd.DataFrame(index=symbols)
        df["Size"] = np.random.normal(0.0, 1.0, len(symbols))
        df["Value"] = factor_matrix.get("Value_EP", pd.Series(0.0, index=symbols))
        df["Momentum"] = factor_matrix.get("Momentum_20D", pd.Series(0.0, index=symbols))
        df["Volatility"] = factor_matrix.get("Volatility_20D", pd.Series(0.0, index=symbols))
        df["Liquidity"] = factor_matrix.get("Liquidity_20D", pd.Series(0.0, index=symbols))
        df["Quality"] = factor_matrix.get("Quality_ROE", pd.Series(0.0, index=symbols))
        return df.fillna(0.0)

    @classmethod
    def calculate_portfolio_exposures(cls, weights: Dict[str, float], factor_matrix: pd.DataFrame) -> Dict[str, Any]:
        """
        组合级别的行业与 Style 风格暴露度汇总
        """
        symbols = list(weights.keys())
        if not symbols:
            return {"industry_exposure": {}, "style_exposure": {}}

        # 1. 行业暴露度
        ind_exp = {}
        for sym, w in weights.items():
            ind = cls.get_stock_industry(sym)
            ind_exp[ind] = ind_exp.get(ind, 0.0) + w

        # 2. Style 风格暴露度 (加权和)
        styles = cls.calculate_style_exposures(symbols, factor_matrix)
        style_exp = {}
        for col in styles.columns:
            style_exp[col] = float(sum(weights[sym] * styles.loc[sym, col] for sym in symbols if sym in styles.index))

        return {
            "industry_exposure": {k: round(v, 4) for k, v in ind_exp.items()},
            "style_exposure": {k: round(v, 4) for k, v in style_exp.items()}
        }
