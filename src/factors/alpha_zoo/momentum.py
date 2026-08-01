"""
momentum.py
Momentum 动量类因子族: MOM_5D, MOM_20D, MOM_60D
保留准确版权与学术引用 (Academic / Microsoft Qlib)
"""

import pandas as pd
import numpy as np
from src.factors.alpha_zoo.schema import AlphaDefinition


def compute_mom_5d(df: pd.DataFrame) -> pd.Series:
    """MOM_5D: 5日价格动量 (close[t] / close[t-5] - 1.0)"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        res = df_sorted.groupby("symbol")["close"].pct_change(periods=5)
        return res
    return df["close"].pct_change(periods=5)


def compute_mom_20d(df: pd.DataFrame) -> pd.Series:
    """MOM_20D: 20日价格动量 (close[t] / close[t-20] - 1.0)"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        res = df_sorted.groupby("symbol")["close"].pct_change(periods=20)
        return res
    return df["close"].pct_change(periods=20)


def compute_mom_60d(df: pd.DataFrame) -> pd.Series:
    """MOM_60D: 60日价格动量 (close[t] / close[t-60] - 1.0)"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        res = df_sorted.groupby("symbol")["close"].pct_change(periods=60)
        return res
    return df["close"].pct_change(periods=60)


MOM_5D_DEF = AlphaDefinition(
    alpha_id="MOM_5D",
    name="5D Price Momentum",
    category="Momentum",
    description="5个交易日短期价格动量 (Short-term Price Change Rate)",
    formula="close[t] / close[t-5] - 1.0",
    required_fields=["close"],
    warmup_period=5,
    holding_period=3,
    frequency="daily",
    source="Microsoft Qlib / Jegadeesh & Titman (1993)",
    license="MIT",
    attribution="Source: Microsoft Qlib (MIT) & Academic Literature",
    original_reference="Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_mom_5d
)

MOM_20D_DEF = AlphaDefinition(
    alpha_id="MOM_20D",
    name="20D Price Momentum",
    category="Momentum",
    description="20个交易日中期价格动量 (Medium-term Price Momentum)",
    formula="close[t] / close[t-20] - 1.0",
    required_fields=["close"],
    warmup_period=20,
    holding_period=5,
    frequency="daily",
    source="Microsoft Qlib / Jegadeesh & Titman (1993)",
    license="MIT",
    attribution="Source: Microsoft Qlib (MIT) & Academic Literature",
    original_reference="Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_mom_20d
)

MOM_60D_DEF = AlphaDefinition(
    alpha_id="MOM_60D",
    name="60D Price Momentum",
    category="Momentum",
    description="60个交易日长中周期动量",
    formula="close[t] / close[t-60] - 1.0",
    required_fields=["close"],
    warmup_period=60,
    holding_period=10,
    frequency="daily",
    source="Microsoft Qlib / Academic Literature",
    license="MIT",
    attribution="Source: Microsoft Qlib (MIT)",
    original_reference="Fama, E. F., & French, K. R. (1996). Multifactor explanations of asset pricing anomalies.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_mom_60d
)
