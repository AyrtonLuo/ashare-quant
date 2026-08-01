"""
models.py
统一行情数据模型 (MarketData) 包含真实数据血缘 (Data Provenance & Lineage Metadata)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class MarketData:
    symbol: str
    timestamp: Optional[str] = None  # YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: float = 0.0
    amount: float = 0.0
    change_pct: float = 0.0
    name: str = ""
    source: Optional[str] = None      # "AkShare", "Tencent", "Local Parquet Cache", "DemoProvider"
    data_mode: str = "RESEARCH"        # "RESEARCH" 或 "DEMO"
    is_real: bool = True               # 真实行情标记
    status: str = "AVAILABLE"          # "AVAILABLE" 或 "DATA_UNAVAILABLE"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "change_pct": self.change_pct,
            "name": self.name,
            "source": self.source,
            "data_mode": self.data_mode,
            "is_real": self.is_real,
            "status": self.status
        }
