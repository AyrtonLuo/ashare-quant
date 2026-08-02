"""
corporate_action.py — Corporate Action Contract (Dividends, Splits, Bonus Shares).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CorporateActionContract:
    symbol: str               # "600519.SH"
    ex_date: str              # Effective date "YYYY-MM-DD"
    action_type: str          # "CASH_DIVIDEND", "BONUS_ISSUE", "RIGHTS_OFFERING", "STOCK_SPLIT"
    cash_amount_per_share: float # Cash dividend per share (RMB)
    bonus_ratio: float        # Bonus shares per share
    split_ratio: float        # Split ratio (e.g. 2.0 for 1-to-2 split)
    announcement_date: str    # Disclosure date
    quality_status: str       # "VALID", "SUSPECT"
