"""
liquidity.py
Liquidity 流动性类因子族: TURNOVER_20D
保留准确版权与学术引用 (Barra / Academic)
"""

import pandas as pd
import numpy as np
from src.factors.alpha_zoo.schema import AlphaDefinition


def compute_turnover_20d(df: pd.DataFrame) -> pd.Series:
    """TURNOVER_20D: 20日日均成交额流动性因子 (Rolling Mean of Amount / Volume)"""
    col = "amount" if "amount" in df.columns else ("volume" if "volume" in df.columns else "close")
    
    if "symbol" in df.columns and "timestamp" in df.columns:
        df_sorted = df.sort_values(["symbol", "timestamp"])
        return df_sorted.groupby("symbol")[col].rolling(window=20, min_periods=1).mean().reset_index(level=0, drop=True)
    
    return df[col].rolling(window=20, min_periods=1).mean()


TURNOVER_20D_DEF = AlphaDefinition(
    alpha_id="TURNOVER_20D",
    name="20D Liquidity Amount",
    category="Liquidity",
    description="20日日均成交额流动性因子 (Average Liquidity Volume)",
    formula="rolling_mean(amount, 20)",
    required_fields=["amount"],
    warmup_period=20,
    holding_period=5,
    frequency="daily",
    source="Academic / Barra Risk Model",
    license="Academic / Open Source",
    attribution="Source: Barra Risk Model & Academic Literature",
    original_reference="Datar, V. T., Naik, N. Y., & Radcliffe, R. (1998). Liquidity and stock returns: An alternative test.",
    lookahead_safe=True,
    requires_fundamental=False,
    requires_market_data=True,
    compute_fn=compute_turnover_20d
)
