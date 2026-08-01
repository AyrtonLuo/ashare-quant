"""
reversal.py
Reversal 反转类因子族: REV_5D, REV_20D
保留准确版权与学术引用 (Kakushadze 101 / GTJA 191 / Academic)
"""

import pandas as pd
import numpy as np
from src.factors.alpha_zoo.schema import AlphaDefinition


def compute_rev_5d(df: pd.DataFrame) -> pd.Series:
    """REV_5D: 5日均值回归/反转因子 (-1.0 * (close[t] / close[t-5] - 1.0))"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        return -1.0 * df_sorted.groupby("symbol")["close"].pct_change(periods=5)
    return -1.0 * df["close"].pct_change(periods=5)


def compute_rev_20d(df: pd.DataFrame) -> pd.Series:
    """REV_20D: 20日均值回归/反转因子 (-1.0 * (close[t] / close[t-20] - 1.0))"""
    if "close" not in df.columns:
        raise ValueError("DataFrame 缺失 'close' 列")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        return -1.0 * df_sorted.groupby("symbol")["close"].pct_change(periods=20)
    return -1.0 * df["close"].pct_change(periods=20)


REV_5D_DEF = AlphaDefinition(
    alpha_id="REV_5D",
    name="5D Reversal",
    category="Reversal",
    description="5日短期价格反转 (Short-term Mean Reversion)",
    formula="-1.0 * (close[t] / close[t-5] - 1.0)",
    required_fields=["close"],
    warmup_period=5,
    holding_period=3,
    frequency="daily",
    source="Kakushadze 101 Alphas / GTJA 191",
    license="Public Domain / Academic",
    attribution="Source: Kakushadze (2016) '101 Formulaic Alphas'",
    original_reference="Kakushadze, Z. (2016). 101 formulaic alphas. Social Science Research Network.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_rev_5d
)

REV_20D_DEF = AlphaDefinition(
    alpha_id="REV_20D",
    name="20D Reversal",
    category="Reversal",
    description="20日中期价格反转 (Medium-term Mean Reversion)",
    formula="-1.0 * (close[t] / close[t-20] - 1.0)",
    required_fields=["close"],
    warmup_period=20,
    holding_period=5,
    frequency="daily",
    source="Kakushadze 101 Alphas / Academic Literature",
    license="Public Domain / Academic",
    attribution="Source: Kakushadze (2016) '101 Formulaic Alphas'",
    original_reference="Kakushadze, Z. (2016). 101 formulaic alphas. Social Science Research Network.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_rev_20d
)
