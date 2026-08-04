"""
pit_gate.py — Point-in-Time (PIT) Protection Gatekeeper for Backtesting & Analysis.
"""

from datetime import datetime
from typing import List
from src.data.contracts.temporal import TemporalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.contracts.fundamental_data import FundamentalDataContract


class PITGate:
    """Enforces that no data with available_at > as_of_cutoff can be accessed."""

    @staticmethod
    def filter_pit_contracts(
        contracts: List[TemporalDataContract], as_of_cutoff: datetime
    ) -> List[TemporalDataContract]:
        """Returns only contracts legally available at as_of_cutoff time (Zero Look-Ahead Bias)."""
        return [c for c in contracts if c.available_at <= as_of_cutoff]

    @staticmethod
    def is_pit_valid(contract: TemporalDataContract, as_of_cutoff: datetime) -> bool:
        return contract.available_at <= as_of_cutoff

    @staticmethod
    def filter_pit_corporate_actions(
        actions: List[CorporateActionContract], as_of_cutoff: datetime
    ) -> List[CorporateActionContract]:
        """Returns only corporate actions legally known at as_of_cutoff time. Filters strictly
        on available_at (disclosure/ingestion visibility), never on ex_date/effective_date —
        an action's economic effective date and its PIT availability are separate concepts."""
        return [a for a in actions if a.available_at <= as_of_cutoff]

    @staticmethod
    def filter_pit_fundamentals(
        records: List[FundamentalDataContract], as_of_cutoff: datetime
    ) -> List[FundamentalDataContract]:
        """Returns only fundamental records legally visible at as_of_cutoff: both available_at
        and received_at must be set and <= as_of_cutoff. A record with either timestamp unset
        (None) is excluded rather than treated as always-available — an unknown availability
        time can never satisfy a PIT check."""
        return [
            r for r in records
            if r.available_at is not None and r.received_at is not None
            and r.available_at <= as_of_cutoff and r.received_at <= as_of_cutoff
        ]
