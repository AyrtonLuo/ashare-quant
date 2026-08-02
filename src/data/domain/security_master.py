"""
security_master.py — Security Master Domain Model & Registry.
"""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class SecurityMasterContract:
    symbol: str               # "600519.SH"
    exchange: str             # "SSE", "SZSE", "BSE"
    display_name: str         # "贵州茅台"
    security_type: str        # "STOCK", "INDEX", "ETF", "OPTION"
    list_date: str            # "YYYY-MM-DD"
    delist_date: Optional[str] # "YYYY-MM-DD" or None
    status: str               # "ACTIVE", "DELISTED", "SUSPENDED"
    industry_sw_l1: str       # "食品饮料"
    industry_sw_l2: str       # "白酒"


class SecurityMasterRegistry:
    """Security Master Registry providing universe lookup without Survivorship Bias."""

    def __init__(self):
        self._securities: Dict[str, SecurityMasterContract] = {}

    def register(self, security: SecurityMasterContract):
        self._securities[security.symbol] = security

    def get_security(self, symbol: str) -> Optional[SecurityMasterContract]:
        return self._securities.get(symbol)

    def is_tradable_on(self, symbol: str, trade_date: str) -> bool:
        sec = self.get_security(symbol)
        if not sec:
            return False
        if trade_date < sec.list_date:
            return False
        if sec.delist_date and trade_date >= sec.delist_date:
            return False
        return sec.status != "SUSPENDED"
