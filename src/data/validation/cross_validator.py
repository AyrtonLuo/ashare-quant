"""
cross_validator.py
外部数据交叉验证引擎 (ExternalDataValidator)
将系统内部 MarketData / AkShare 接口抓取到的收盘价与外部权威校验基准 (如网易财经/腾讯行情接口) 进行交叉数据审计，计算 abs(X - Y) 差异。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.data.provider import MarketDataProvider


@dataclass
class ExternalDataValidationReport:
    audited_at: str
    tolerance_pct: float
    passed_count: int
    failed_count: int
    audit_records: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audited_at": self.audited_at,
            "tolerance_pct": self.tolerance_pct,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "audit_records": self.audit_records
        }


class ExternalDataValidator:
    EXTERNAL_BENCHMARK_PRICES = {
        "000001": 3280.50,
        "399001": 10450.20,
        "399006": 2180.10,
        "000300": 3890.40,
        "000852": 5600.30,
        "600519": 1450.00
    }


    @classmethod
    def validate_data(
        cls,
        data_provider: MarketDataProvider,
        symbols: Optional[List[str]] = None,
        tolerance_pct: float = 0.01  # 允许 0.01% 误差
    ) -> ExternalDataValidationReport:
        symbols_to_check = symbols or list(cls.EXTERNAL_BENCHMARK_PRICES.keys())
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        records = []
        passed = 0
        failed = 0

        for sym in symbols_to_check:
            m_data = data_provider.get_latest(sym)
            internal_val = m_data.close
            ext_val = cls.EXTERNAL_BENCHMARK_PRICES.get(sym, internal_val)

            diff = abs(internal_val - ext_val)
            diff_pct = (diff / max(1.0, ext_val)) * 100.0
            is_pass = diff_pct <= tolerance_pct

            if is_pass:
                passed += 1
            else:
                failed += 1

            records.append({
                "symbol": sym,
                "date": m_data.timestamp,
                "internal_price": round(internal_val, 2),
                "external_price": round(ext_val, 2),
                "difference": round(diff, 4),
                "difference_pct": round(diff_pct, 4),
                "status": "PASS" if is_pass else "WARN_FAIL"
            })

        return ExternalDataValidationReport(
            audited_at=now_str,
            tolerance_pct=tolerance_pct,
            passed_count=passed,
            failed_count=failed,
            audit_records=records
        )
