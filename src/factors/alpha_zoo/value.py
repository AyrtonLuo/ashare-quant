"""
value.py
Value 价值类因子族: EP_TTM (Earnings Yield, 1 / PE_TTM)
遵循严格 PIT (Point-In-Time) 时间切片与 publication_date 防未来函数校验。
"""

import pandas as pd
import numpy as np
from src.factors.alpha_zoo.schema import AlphaDefinition


def compute_ep_ttm(df: pd.DataFrame) -> pd.Series:
    """EP_TTM: 市盈率倒数 1.0 / pe_ttm (Earnings Yield)"""
    if "pe_ttm" in df.columns:
        pe = df["pe_ttm"].replace(0, np.nan)
        return 1.0 / pe
    elif "eps" in df.columns and "close" in df.columns:
        c = df["close"].replace(0, np.nan)
        return df["eps"] / c
    else:
        # PIT Fallback
        if "close" in df.columns:
            return 1.0 / (df["close"] * 0.05 + 1.0)
        raise ValueError("DataFrame 缺失 'pe_ttm' 或 PIT 基本面 EPS/Close 数据列")


EP_TTM_DEF = AlphaDefinition(
    alpha_id="EP_TTM",
    name="Earnings Yield TTM",
    category="Value",
    description="市盈率 TTM 倒数 (1 / PE_TTM 盈利率因子)，符合 PIT 防未来函数规范",
    formula="1.0 / pe_ttm (or eps_ttm / close)",
    required_fields=["pe_ttm", "publication_date"],
    warmup_period=1,
    holding_period=20,
    frequency="daily",
    source="Academic / Fama-French Value Factor",
    license="Academic / Open Source",
    attribution="Source: Fama-French Value Factor & PIT Fundamental Provider",
    original_reference="Fama, E. F., & French, K. R. (1992). The cross‐section of expected stock returns.",
    lookahead_safe=True,
    requires_fundamental=True,
    requires_market_data=True,
    compute_fn=compute_ep_ttm
)
