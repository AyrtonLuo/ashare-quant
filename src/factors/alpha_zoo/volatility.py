"""
volatility.py
Volatility 波动率类因子族: VOL_20D
保留准确版权与学术引用 (Academic / Qlib)
"""

import pandas as pd
import numpy as np
from src.factors.alpha_zoo.schema import AlphaDefinition


def compute_vol_20d(df: pd.DataFrame) -> pd.Series:
    """VOL_20D: 20日收益率标准差 (20-day Annualized Volatility)"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        returns = df_sorted.groupby("symbol")["close"].pct_change()
        vol = returns.groupby(df_sorted["symbol"]).rolling(window=20, min_periods=5).std().reset_index(level=0, drop=True)
        return vol * np.sqrt(252)
    
    returns = df["close"].pct_change()
    return returns.rolling(window=20, min_periods=5).std() * np.sqrt(252)


VOL_20D_DEF = AlphaDefinition(
    alpha_id="VOL_20D",
    name="20D Volatility",
    category="Volatility",
    description="20日年化收益率波动率 (Annualized Volatility)",
    formula="std(pct_change(close, 1), 20) * sqrt(252)",
    required_fields=["close"],
    warmup_period=20,
    holding_period=5,
    frequency="daily",
    source="Academic / Barra Risk Model",
    license="Academic / Open Source",
    attribution="Source: Barra Risk Model & Academic Literature",
    original_reference="Ang, A., Hodrick, R. J., Xing, Y., & Zhang, X. (2006). The cross‐section of volatility and expected returns.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_vol_20d
)
