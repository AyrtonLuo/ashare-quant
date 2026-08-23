"""
corporate_action.py — Corporate Action Contract (Dividends, Splits, Bonus Shares).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class CorporateActionContract:
    symbol: str               # "600519.SH"
    ex_date: str              # Effective date "YYYY-MM-DD" (the date the action takes economic effect)
    action_type: str          # "CASH_DIVIDEND", "BONUS_ISSUE", "RIGHTS_OFFERING", "STOCK_SPLIT"
    cash_amount_per_share: float # Cash dividend per share (RMB)
    bonus_ratio: float        # Bonus shares per share
    split_ratio: float        # Split ratio (e.g. 2.0 for 1-to-2 split)
    announcement_date: str    # Disclosure date (event_time — when the action was publicly announced)

    # PIT visibility. NOT derived from ex_date/effective_date (an action's economic effective
    # date is a separate concept from when the system could legally know about it). Must be
    # set from the actual disclosure/ingestion timestamp — never from datetime.now() as a
    # substitute for historical availability.
    available_at: datetime    # When this action became legally visible to PIT queries
    received_at: datetime     # When this action's payload arrived in the system

    quality_status: str       # "VALID", "SUSPECT"

    # Provenance: REAL_PROVIDER | LOCAL_PRODUCTION_VERIFICATION_DATA | GOLDEN_DATASET | SYNTHETIC_DATA
    # Defaults to SYNTHETIC_DATA (fail-closed). Only a code path that actually parsed a live
    # network provider response may set REAL_PROVIDER.
    data_origin: str = "SYNTHETIC_DATA"

    # RIGHTS_OFFERING (配股) economic parameters. Trailing-defaulted so all existing construction
    # call sites remain valid unmodified; only meaningful when action_type == "RIGHTS_OFFERING".
    # A RIGHTS_OFFERING action with either field left None fails closed in
    # CorporateActionAdjuster rather than being treated as ratio 0.0 (see
    # RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md §4).
    rights_ratio: Optional[float] = None        # new shares per share held, e.g. 0.3 for "10配3"
    subscription_price: Optional[float] = None  # RMB price paid per new share
