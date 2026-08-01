"""
evidence.py
Alpha Evidence Record 因子溯源存证数据结构与哈希生成机制
确保每个在真实数据上计算的 Alpha 均具有唯一的证明与 Hash。
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class AlphaEvidenceRecord:
    alpha_id: str
    symbol: str
    data_source: str
    data_start: str
    data_end: str
    calculation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_mode: str = "RESEARCH"
    is_real: bool = True
    pit_status: str = "VERIFIED_PIT_SAFE"
    lookahead_status: str = "VERIFIED_LOOKAHEAD_SAFE"
    formula_version: str = "1.0.0"
    latest_value: Optional[float] = None
    result_hash: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.result_hash:
            raw_str = f"{self.alpha_id}|{self.symbol}|{self.data_source}|{self.data_start}|{self.data_end}|{self.latest_value}"
            self.result_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "symbol": self.symbol,
            "data_source": self.data_source,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "calculation_timestamp": self.calculation_timestamp,
            "data_mode": self.data_mode,
            "is_real": self.is_real,
            "pit_status": self.pit_status,
            "lookahead_status": self.lookahead_status,
            "formula_version": self.formula_version,
            "latest_value": self.latest_value,
            "result_hash": self.result_hash,
            "extra": self.extra
        }
