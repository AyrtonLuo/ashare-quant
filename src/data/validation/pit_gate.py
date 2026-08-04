"""
pit_gate.py — Point-in-Time (PIT) Protection Gatekeeper for Backtesting & Analysis.
"""

from datetime import datetime
from typing import List
from src.data.contracts.temporal import TemporalDataContract
from src.data.contracts.corporate_action import CorporateActionContract


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
