"""
composite_factor.py
复合 Alpha 因子合成模块：基于历史滚动 IC-IR 权重（防未来函数）结合动量 (MOM_20) 与低波动率 (LOW_VOL_20) 因子。
"""

import pandas as pd
import numpy as np
import scipy.stats as stats
from src.strategy.factors import mad_clip_series, zscore_series, preprocess_factors_cross_section


def compute_historical_ic_series(df: pd.DataFrame, factor_col: str) -> pd.Series:
    """
    计算截至每日的单日 IC 序列 (用于滚动/扩展窗口计算历史 IC-IR 权重)
    """
    data = df.copy()
    data['forward_return_1d'] = data.groupby('symbol')['close'].transform(lambda s: s.shift(-1) / s - 1.0)
    
    ic_dict = {}
    for date, group in data.groupby('date'):
        valid = group[[factor_col, 'forward_return_1d']].dropna()
        if len(valid) >= 3:
            rank_ic, _ = stats.spearmanr(valid[factor_col], valid['forward_return_1d'])
            if not np.isnan(rank_ic):
                ic_dict[date] = rank_ic
                
    return pd.Series(ic_dict)


def build_composite_alpha_factor(df: pd.DataFrame, method: str = "equal_weight") -> pd.DataFrame:
    """
    合成复合 Alpha 因子 (MOM_20 + LOW_VOL_20)
    
    参数:
        df: 包含预处理后因子的 DataFrame (包含 'MOM_20_norm', 'LOW_VOL_20_norm')
        method: "equal_weight" (等权) 或 "dynamic_ic_ir" (基于历史扩展窗口的动态 IC-IR 加权)
        
    返回:
        增加了 'COMPOSITE_ALPHA_norm' 列的 DataFrame
    """
    data = df.copy()
    data = data.sort_values(['date', 'symbol']).reset_index(drop=True)
    
    if method == "equal_weight":
        # 等权重基准合成
        data['COMPOSITE_ALPHA_raw'] = 0.5 * data['MOM_20_norm'] + 0.5 * data['LOW_VOL_20_norm']
    
    elif method == "dynamic_ic_ir":
        # =========================================================================
        # 🚨 【IC-IR 权重防未来函数 (Lookahead Bias Prevention)】:
        # 在第 T 日合成复合因子时，计算权重使用的 IC-IR 只能基于截至 T-1 日的历史 IC 序列。
        # 绝不使用全样本统一 IC-IR 加权！
        # =========================================================================
        ic_mom = compute_historical_ic_series(data, "MOM_20_norm")
        ic_low_vol = compute_historical_ic_series(data, "LOW_VOL_20_norm")
        
        unique_dates = data['date'].drop_duplicates().sort_values().reset_index(drop=True)
        composite_raw = pd.Series(index=data.index, dtype=float)
        
        for i, curr_date in enumerate(unique_dates):
            # 获取截至前一日 (T-1) 的历史 IC 序列
            hist_mom = ic_mom[ic_mom.index < curr_date]
            hist_low_vol = ic_low_vol[ic_low_vol.index < curr_date]
            
            # 若历史样本不足 20 日，默认设为等权 0.5 / 0.5
            if len(hist_mom) < 20 or len(hist_low_vol) < 20:
                w_mom = 0.5
                w_low_vol = 0.5
            else:
                ir_mom = max(0.0, hist_mom.mean() / hist_mom.std()) if hist_mom.std() > 0 else 0.0
                ir_low_vol = max(0.0, hist_low_vol.mean() / hist_low_vol.std()) if hist_low_vol.std() > 0 else 0.0
                
                total_ir = ir_mom + ir_low_vol
                if total_ir > 0:
                    w_mom = ir_mom / total_ir
                    w_low_vol = ir_low_vol / total_ir
                else:
                    w_mom = 0.5
                    w_low_vol = 0.5

            mask = (data['date'] == curr_date)
            composite_raw[mask] = w_mom * data.loc[mask, 'MOM_20_norm'] + w_low_vol * data.loc[mask, 'LOW_VOL_20_norm']
            
        data['COMPOSITE_ALPHA_raw'] = composite_raw
        
    else:
        raise ValueError(f"未知的合成方法: {method}")

    # 最后对合成因子在每日横截面上再做一次 Z-Score 标准化 (防御性 fillna)
    def process_series(s):
        if s.dropna().empty or len(s.dropna()) < 3:
            return s.fillna(0.0)
        res = zscore_series(mad_clip_series(s))
        return res.fillna(0.0)
        
    data['COMPOSITE_ALPHA_norm'] = data.groupby('date')['COMPOSITE_ALPHA_raw'].transform(process_series).fillna(0.0)
    data['COMPOSITE_ALPHA'] = data['COMPOSITE_ALPHA_norm']
    return data
