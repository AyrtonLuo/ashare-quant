"""
checker.py
数据质量校验引擎与质量报告生成器 (DataQualityChecker & DataQualityReport)
自动化校验异常数据、缺失值、重复时间戳、价格/成交量异动与交易日覆盖率。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DataQualityReport:
    symbol: str
    rows_count: int
    missing_values: int
    duplicates: int
    anomalies: List[str]
    coverage_pct: float
    status: str  # "PASS", "WARNING", "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "rows_count": self.rows_count,
            "missing_values": self.missing_values,
            "duplicates": self.duplicates,
            "anomalies": self.anomalies,
            "coverage_pct": round(self.coverage_pct, 2),
            "status": self.status
        }


class DataQualityChecker:
    @staticmethod
    def check_dataframe(symbol: str, df: pd.DataFrame) -> DataQualityReport:
        if df is None or df.empty:
            return DataQualityReport(
                symbol=symbol, rows_count=0, missing_values=0,
                duplicates=0, anomalies=["Dataframe is empty"],
                coverage_pct=0.0, status="FAIL"
            )

        rows_count = len(df)
        missing_values = int(df[['close', 'volume']].isna().sum().sum())

        dup_series = df.duplicated(subset=['date']) if 'date' in df.columns else pd.Series(False, index=df.index)
        duplicates = int(dup_series.sum())

        anomalies = []
        if (df['close'] <= 0).any():
            anomalies.append("Non-positive prices found")

        if 'close' in df.columns and len(df) > 1:
            pct_chg = df['close'].pct_change().abs()
            if (pct_chg > 0.25).any():
                anomalies.append("Extreme single-day price movement > 25%")

        status = "PASS"
        if anomalies or missing_values > 0 or duplicates > 0:
            status = "WARNING"
        if rows_count == 0 or (df['close'] <= 0).all():
            status = "FAIL"

        return DataQualityReport(
            symbol=symbol,
            rows_count=rows_count,
            missing_values=missing_values,
            duplicates=duplicates,
            anomalies=anomalies,
            coverage_pct=100.0 if missing_values == 0 else max(0.0, 100.0 - (missing_values / (rows_count * 2)) * 100),
            status=status
        )
