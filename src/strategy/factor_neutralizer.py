"""
factor_neutralizer.py
机构级因子预处理模块：
1. 行业与市值中性化 (Market Cap & Industry Neutralization via Cross-Sectional OLS)
2. 因子对称正交化 (Löwdin Symmetric Orthogonalization)
"""

import numpy as np
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("factor_neutralizer")

# 申万一级行业常用虚拟分类映射 (根据股票代码与市值模拟分类，确保无外部依赖)
SW_INDUSTRIES = [
    "银行", "非银金融", "电子", "医药生物", "电力设备",
    "食品饮料", "计算机", "机械设备", "汽车", "基础化工"
]


def assign_industry_category(symbol: str) -> str:
    """根据股票代码哈希分配申万一级行业 (确保横截面行业分布确定性)"""
    idx = int(str(symbol).zfill(6)[-2:]) % len(SW_INDUSTRIES)
    return SW_INDUSTRIES[idx]


def neutralize_factor(df: pd.DataFrame, factor_col: str, market_cap_col: str = "total_mv_yi") -> pd.Series:
    """
    单日横截面市值与行业中性化 (OLS 多元线性回归提取残差)
    Factor_raw = alpha + beta * log(MarketCap) + sum(gamma_j * Industry_j) + epsilon
    返回中性化并 Z-Score 标准化后的残差 epsilon
    """
    data = df.copy()
    
    # 若缺失总市值，用收盘价平替以防止 log(0)
    if market_cap_col not in data.columns or data[market_cap_col].isnull().all():
        data['log_mc'] = np.log(np.maximum(data['close'], 1.0))
    else:
        data['log_mc'] = np.log(np.maximum(data[market_cap_col].fillna(data['close']), 1.0))
        
    # 分配申万行业分类
    if 'industry' not in data.columns:
        data['industry'] = data['symbol'].apply(assign_industry_category)
        
    # 生成行业 Dummy 虚拟变量
    ind_dummies = pd.get_dummies(data['industry'], prefix='ind', drop_first=True)
    
    # 构造回归自变量 X = [1, log_mc, Industry_Dummies]
    X_cols = pd.concat([pd.Series(1.0, index=data.index, name='const'), data['log_mc'], ind_dummies], axis=1).astype(float)
    
    # 目标因变量 Y
    Y = data[factor_col].astype(float).values
    X_mat = X_cols.values
    
    # 处理 NaN 值
    valid_mask = ~np.isnan(Y) & ~np.isnan(X_mat).any(axis=1)
    
    neutral_factor = np.full(len(df), np.nan)
    
    if np.sum(valid_mask) > X_mat.shape[1]:
        X_valid = X_mat[valid_mask]
        Y_valid = Y[valid_mask]
        
        # OLS 最小二乘求解 beta
        try:
            beta, residuals, rank, s = np.linalg.lstsq(X_valid, Y_valid, rcond=None)
            Y_pred = X_valid @ beta
            raw_residuals = Y_valid - Y_pred
            
            # 残差 Z-Score 标准化
            std_res = np.std(raw_residuals)
            if std_res > 1e-12:
                norm_residuals = (raw_residuals - np.mean(raw_residuals)) / std_res
            else:
                norm_residuals = raw_residuals
                
            neutral_factor[valid_mask] = norm_residuals
        except Exception as e:
            logger.warning(f"横截面 OLS 中性化回归计算失败: {e}")
            neutral_factor = Y
            
    return pd.Series(neutral_factor, index=df.index, name=f"{factor_col}_neu")


def neutralize_factors_cross_section(df: pd.DataFrame, factor_cols: list[str], market_cap_col: str = "total_mv_yi") -> pd.DataFrame:
    """
    按交易日对多因子执行逐日横截面市值与行业中性化
    """
    res_df = df.copy()
    
    for factor_col in factor_cols:
        neu_series = res_df.groupby('date', group_keys=False).apply(
            lambda group: neutralize_factor(group, factor_col, market_cap_col=market_cap_col)
        )
        res_df[f"{factor_col}_neu"] = neu_series
        res_df[f"{factor_col}_neu_norm"] = neu_series
        
    return res_df


def orthogonalize_factors(df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    """
    多因子对称正交化 (Löwdin Symmetric Orthogonalization)
    消除因子间的非零相关性，同时保持与原始因子最大相关度 (F_orth = F * M^(-1/2))
    """
    res_df = df.copy()
    
    # 按交易日逐日执行横截面对称正交化
    grouped = res_df.groupby('date')
    
    orth_factor_matrices = []
    indices = []
    
    for date, group in grouped:
        F_mat = group[factor_cols].values
        valid_mask = ~np.isnan(F_mat).any(axis=1)
        
        orth_mat = np.full_like(F_mat, np.nan)
        
        if np.sum(valid_mask) > len(factor_cols):
            F_valid = F_mat[valid_mask]
            
            # 中心化
            F_mean = np.mean(F_valid, axis=0)
            F_centered = F_valid - F_mean
            
            # 1. 计算因子协方差重叠矩阵 M = F^T F
            M = F_centered.T @ F_centered
            
            # 2. 描述特征值分解 M = V * Lambda * V^T
            eigvals, V = np.linalg.eigh(M)
            
            # 正定保护
            eigvals = np.maximum(eigvals, 1e-8)
            
            # 3. 计算 M^(-1/2) = V * Lambda^(-1/2) * V^T
            Lambda_inv_sqrt = np.diag(1.0 / np.sqrt(eigvals))
            M_inv_sqrt = V @ Lambda_inv_sqrt @ V.T
            
            # 4. 对称正交化因子矩阵 F_orth = F * M^(-1/2)
            F_orth_valid = F_centered @ M_inv_sqrt
            
            # 标准化正交结果
            std_orth = np.std(F_orth_valid, axis=0)
            std_orth = np.where(std_orth > 1e-12, std_orth, 1.0)
            F_orth_valid = F_orth_valid / std_orth
            
            orth_mat[valid_mask] = F_orth_valid
            
        orth_factor_matrices.append(orth_mat)
        indices.extend(group.index.tolist())
        
    orth_all = np.vstack(orth_factor_matrices)
    
    for i, col in enumerate(factor_cols):
        res_df.loc[indices, f"{col}_orth"] = orth_all[:, i]
        
    return res_df
