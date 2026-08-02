"""
pit_gate.py — Point-in-Time (PIT) Protection Gatekeeper for Backtesting & Analysis.
"""

from datetime import datetime
from typing import List
from src.data.contracts.temporal import TemporalDataContract


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
