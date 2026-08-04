"""
security_master.py — Security Master Domain Model & Point-in-Time Universe Registry.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Set, List


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
    """
    Security Master Registry providing universe lookup without Survivorship Bias
    and with Point-in-Time historical trading state tracking.
    """

    def __init__(self):
        self._securities: Dict[str, SecurityMasterContract] = {}
        # Key: trade_date -> Set of suspended symbols on that specific date
        self._suspensions_by_date: Dict[str, Set[str]] = {}

    def register(self, security: SecurityMasterContract):
        self._securities[security.symbol] = security

    def register_suspension(self, symbol: str, trade_date: str):
        """Registers a historical suspension for a specific symbol on a specific trading date."""
        if trade_date not in self._suspensions_by_date:
            self._suspensions_by_date[trade_date] = set()
        self._suspensions_by_date[trade_date].add(symbol)

    def get_security(self, symbol: str) -> Optional[SecurityMasterContract]:
        return self._securities.get(symbol)

    def is_suspended_on(self, symbol: str, trade_date: str) -> bool:
        """Returns True if the security was suspended on the given trade_date."""
        return symbol in self._suspensions_by_date.get(trade_date, set())

    def is_tradable_on(self, symbol: str, trade_date: str) -> bool:
        """
        Determines whether symbol was tradable on trade_date under PIT rules.
        Filters listing date, delisting date, and point-in-time suspension state on trade_date.
        """
        sec = self.get_security(symbol)
        if not sec:
            return False
        if trade_date < sec.list_date:
            return False
        if sec.delist_date and trade_date >= sec.delist_date:
            return False
        return not self.is_suspended_on(symbol, trade_date)

    def get_historical_universe(self, as_of_date: str) -> List[str]:
        """
        Returns all symbols that were listed on or before as_of_date and not delisted on as_of_date.
        Eliminates survivorship bias by retaining historical constituents.
        """
        universe = []
        for symbol, sec in self._securities.items():
            if sec.list_date <= as_of_date:
                if sec.delist_date is None or sec.delist_date > as_of_date:
                    universe.append(symbol)
        universe.sort()
        return universe
