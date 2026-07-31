"""
ma_cross.py
双均线择时策略实现（基于 Pandas 向量化计算）
"""

import pandas as pd
import numpy as np

def generate_ma_cross_signals(df: pd.DataFrame, short_window: int = 5, long_window: int = 10) -> pd.DataFrame:
    """
    生成双均线策略信号
    
    参数:
        df: 包含日线数据的 DataFrame (包含 'date', 'close' 等列)
        short_window: 短期均线周期 (默认 5日)
        long_window: 长期均线周期 (默认 10日)
        
    返回:
        带有均线指标和原始信号 (signal) 的 DataFrame
    """
    data = df.copy()
    data = data.sort_values('date').reset_index(drop=True)
    
    # 1. 计算短期与长期简单移动平均线 (SMA)
    data[f'ma_{short_window}'] = data['close'].rolling(window=short_window).mean()
    data[f'ma_{long_window}'] = data['close'].rolling(window=long_window).mean()
    
    # 2. 生成原始交易信号 (signal):
    # 短期均线 > 长期均线 时产生多头持仓信号 (1)，否则为空仓 (0)
    data['signal'] = np.where(data[f'ma_{short_window}'] > data[f'ma_{long_window}'], 1.0, 0.0)
    
    # 将计算初期由于窗口不足产生 NaN 的信号填充为 0
    data['signal'] = data['signal'].fillna(0.0)
    
    return data
