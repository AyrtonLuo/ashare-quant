"""
history.py
组合历史净值与风险序列记录器 (PortfolioHistory)
记录每交易日 timestamp, cash, market_value, equity, daily_return, drawdown。
"""

import os
import pandas as pd
from typing import Dict, Any, List


class PortfolioHistory:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def record_step(self, timestamp: str, cash: float, market_value: float, equity: float):
        prev_equity = self.records[-1]["equity"] if self.records else equity
        daily_ret = ((equity - prev_equity) / prev_equity) if prev_equity > 0 else 0.0

        equities = [r["equity"] for r in self.records] + [equity]
        peak = max(equities)
        drawdown = ((peak - equity) / peak) if peak > 0 else 0.0

        self.records.append({
            "timestamp": timestamp,
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "equity": round(equity, 2),
            "daily_return": round(daily_ret, 6),
            "drawdown": round(drawdown, 6)
        })

    def to_dataframe(self) -> pd.DataFrame:
        if not self.records:
            return pd.DataFrame(columns=["timestamp", "cash", "market_value", "equity", "daily_return", "drawdown"])
        df = pd.DataFrame(self.records)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["cumulative_return"] = (df["equity"] / df["equity"].iloc[0]) - 1.0
        return df

    def save_parquet(self, filepath: str):
        df = self.to_dataframe()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        df.to_parquet(filepath, index=False)
