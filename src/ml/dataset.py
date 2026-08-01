"""
dataset.py
量化 ML 数据集对齐与构建模块 (MLDatasetBuilder)
生成特征矩阵 X(t) 与 Forward N-Day Return 训练目标 y(t) = Return(t+N)。
特征 X(t) 严格禁止使用 future data，训练目标 y(t) 作为 Label 对齐。
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Any
from src.data.provider import MarketDataProvider
from src.ml.features import FeatureExtractor


class MLDatasetBuilder:
    def __init__(self, data_provider: MarketDataProvider, forward_days: int = 20):
        self.data_provider = data_provider
        self.forward_days = forward_days
        self.extractor = FeatureExtractor(data_provider)

    def build_dataset(self, symbols: List[str], dates: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
        """
        构建包含 (X, y) 的结构化数据集
        X: index=[(date, symbol)], columns=[feature_names]
        y: Series index=[(date, symbol)], values=forward_return
        """
        x_rows = []
        y_rows = []

        for d in dates:
            feat_df = self.extractor.extract_features_on_date(symbols, cutoff_date=d)

            for sym in symbols:
                h_df = self.data_provider.get_history(sym)
                if h_df.empty:
                    continue

                h_df['date_str'] = h_df['date'].astype(str).str[:10]
                matches = h_df[h_df['date_str'] <= d]
                if matches.empty:
                    continue

                curr_idx = matches.index[-1]
                target_idx = curr_idx + self.forward_days
                if target_idx < len(h_df):
                    p_curr = float(h_df['close'].iloc[curr_idx])
                    p_fwd = float(h_df['close'].iloc[target_idx])
                    fwd_ret = (p_fwd - p_curr) / p_curr if p_curr > 0 else 0.0

                    if sym in feat_df.index:
                        row = feat_df.loc[sym].to_dict()
                        row['date'] = d
                        row['symbol'] = sym
                        x_rows.append(row)
                        y_rows.append({'date': d, 'symbol': sym, 'target': fwd_ret})

        if not x_rows:
            return pd.DataFrame(), pd.Series(dtype=float)

        df_x = pd.DataFrame(x_rows).set_index(['date', 'symbol'])
        df_y = pd.DataFrame(y_rows).set_index(['date', 'symbol'])['target']
        return df_x, df_y
