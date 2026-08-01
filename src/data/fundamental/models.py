"""
models.py
Point-in-Time 基础面与估值数据结构定义 (FundamentalData)
必须显式包含 publication_date (财报实际披露日期)，确保历史截面零未来函数泄漏。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class FundamentalData:
    symbol: str
    timestamp: str          # 归属财报期 (如 "2024-12-31")
    publication_date: str   # 实际披露日期 (如 "2025-03-30")
    pe_ttm: float
    pb: float
    roe: float
    eps: float
    revenue_yi: float
    net_income_yi: float
    market_cap_yi: float
    data_source: str = "AkShare Fundamental 2.0 (PIT Verified)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "publication_date": self.publication_date,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "roe": self.roe,
            "eps": self.eps,
            "revenue_yi": self.revenue_yi,
            "net_income_yi": self.net_income_yi,
            "market_cap_yi": self.market_cap_yi,
            "data_source": self.data_source
        }
