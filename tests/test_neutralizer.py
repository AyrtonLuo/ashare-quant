"""
test_neutralizer.py
测试市值与行业中性化 (Neutralization) 与对称正交化 (Löwdin Orthogonalization)
"""

import pytest
import numpy as np
import pandas as pd
from src.strategy.factor_neutralizer import neutralize_factor, orthogonalize_factors


def test_factor_neutralization():
    """测试 OLS 市值与行业中性化消除共线性与残差属性"""
    np.random.seed(42)
    n = 100
    
    # 模拟生成 100 只股票数据
    symbols = [f"{i:06d}" for i in range(1, n + 1)]
    market_cap = np.random.uniform(50, 5000, size=n)
    
    # 基础因子包含明显的市值偏好 (Size Bias)
    raw_factor = 0.8 * np.log(market_cap) + np.random.normal(0, 1, size=n)
    
    df = pd.DataFrame({
        "symbol": symbols,
        "date": "2026-07-31",
        "close": 10.0,
        "total_mv_yi": market_cap,
        "MOM_20": raw_factor
    })
    
    # 中性化
    neu_factor = neutralize_factor(df, "MOM_20", market_cap_col="total_mv_yi")
    df["MOM_20_neu"] = neu_factor
    
    # 校验：中性化后因子与 log(市值) 的相关系数应当降至接近 0 (|r| < 0.1)
    corr_raw = np.corrcoef(raw_factor, np.log(market_cap))[0, 1]
    corr_neu = np.corrcoef(df["MOM_20_neu"], np.log(market_cap))[0, 1]
    
    assert abs(corr_raw) > 0.5, "原始因子应当存在显著市值偏差"
    assert abs(corr_neu) < 0.1, f"中性化后因子与市值相关系数应当降至 0 附近 (当前: {corr_neu:.4f})"


def test_lowdin_orthogonalization():
    """测试 Löwdin 对称正交化消除因子间多重共线性"""
    np.random.seed(42)
    n = 200
    
    # 生成存在高高度共线性的 3 个原始因子
    f1 = np.random.normal(0, 1, size=n)
    f2 = 0.8 * f1 + 0.2 * np.random.normal(0, 1, size=n)
    f3 = 0.7 * f1 + 0.5 * f2 + 0.1 * np.random.normal(0, 1, size=n)
    
    df = pd.DataFrame({
        "symbol": [f"{i:06d}" for i in range(n)],
        "date": "2026-07-31",
        "F1": f1,
        "F2": f2,
        "F3": f3
    })
    
    factor_cols = ["F1", "F2", "F3"]
    df_orth = orthogonalize_factors(df, factor_cols)
    
    orth_cols = [f"{col}_orth" for col in factor_cols]
    orth_matrix = df_orth[orth_cols].values
    
    # 计算正交后因子的协方差/相关系数矩阵
    corr_matrix = np.corrcoef(orth_matrix, rowvar=False)
    
    # 校验：正交化后非对角线相关系数严格趋向于 0 (|r| < 1e-3)
    off_diag = corr_matrix - np.eye(3)
    assert np.max(np.abs(off_diag)) < 1e-2, f"正交化后因子间相关系数应当全为 0 (当前最大非对角相关: {np.max(np.abs(off_diag)):.6f})"
