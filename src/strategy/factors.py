"""
factors.py
多因子计算与预处理模块：支持动量、波动率、均线偏离度因子的计算，
以及每日横截面 MAD 去极值与 Z-Score 标准化。
"""

import pandas as pd
import numpy as np


def calculate_raw_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算基础单因子（基于历史窗口，绝无未来函数）
    
    参数:
        df: 包含多只股票历史日线数据的 DataFrame (包含 'symbol', 'date', 'close' 列)
        
    返回:
        带有原始因子列的 DataFrame
    """
    data = df.copy()
    data = data.sort_values(['symbol', 'date']).reset_index(drop=True)
    
    # 1. 动量因子 (MOM_20): 过去 20 个交易日累计收益率
    # formula: (P_t / P_{t-20}) - 1
    data['MOM_20'] = data.groupby('symbol')['close'].transform(lambda s: s / s.shift(20) - 1.0)
    
    # 2. 波动率因子 (VOL_20): 过去 20 个交易日日收益率的标准差
    # formula: std(r_{t-19..t})
    data['asset_return'] = data.groupby('symbol')['close'].pct_change()
    data['VOL_20'] = data.groupby('symbol')['asset_return'].transform(lambda s: s.rolling(20).std())
    
    # 3. 均线偏离度因子 (MA_DEV_20): (Close - MA20) / MA20
    # formula: (P_t - MA20_t) / MA20_t
    data['ma_20'] = data.groupby('symbol')['close'].transform(lambda s: s.rolling(20).mean())
    data['MA_DEV_20'] = (data['close'] - data['ma_20']) / data['ma_20']
    
    return data


def mad_clip_series(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """
    中位数绝对偏差法 (MAD, Median Absolute Deviation) 去极值
    """
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0:
        return series
    
    # 1.4826 修正系数使 MAD 在正态分布下等于标准差
    threshold = n_mad * 1.4826 * mad
    lower_bound = median - threshold
    upper_bound = median + threshold
    return series.clip(lower=lower_bound, upper=upper_bound)


def zscore_series(series: pd.Series) -> pd.Series:
    """
    Z-Score 标准化：(X - mean) / std
    """
    std = series.std()
    if std == 0 or pd.isna(std):
        return series - series.mean()
    return (series - series.mean()) / std


def preprocess_factors_cross_section(df: pd.DataFrame, factor_cols: list[str]) -> pd.DataFrame:
    """
    每日横截面因子预处理：先 MAD 去极值，再 Z-Score 标准化
    """
    data = df.copy()
    
    # 按日期分组在横截面上预处理
    for factor in factor_cols:
        norm_col_name = f"{factor}_norm"
        
        def process_series(s):
            if s.dropna().empty or len(s.dropna()) < 3:
                return s
            # 1. MAD 去极值
            s_clipped = mad_clip_series(s)
            # 2. Z-Score 标准化
            s_norm = zscore_series(s_clipped)
            return s_norm

        data[norm_col_name] = data.groupby('date')[factor].transform(process_series)

    return data
