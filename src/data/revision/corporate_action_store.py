"""
corporate_action_store.py — Immutable Point-in-Time Corporate Action Store.

Mirrors revision_store.py's semantics for corporate actions: NEW DATA != DELETE OLD DATA ->
append-only storage keyed by (symbol, ex_date, action_type), PIT query returns the revision
that was legally visible (available_at <= as_of) at the given cutoff. If a corporate action
is later corrected (e.g. a restated dividend amount), the old entry is never mutated or
removed — a historical query with an as_of before the correction's available_at continues to
see the original entry.
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from src.data.contracts.corporate_action import CorporateActionContract


class CorporateActionStore:
    """Stores and queries corporate actions adhering strictly to Point-in-Time (PIT) semantics."""

    def __init__(self):
        # Key: (symbol, ex_date, action_type) -> List of CorporateActionContract sorted by available_at
        self._store: Dict[Tuple[str, str, str], List[CorporateActionContract]] = {}

    def add_action(self, action: CorporateActionContract) -> None:
        """Appends a new corporate action revision. Never overwrites or removes prior entries."""
        key = (action.symbol, action.ex_date, action.action_type)
        existing = self._store.setdefault(key, [])
        existing.append(action)
        existing.sort(key=lambda a: a.available_at)

    def query_pit(
        self, symbol: str, ex_date: str, action_type: str, as_of: datetime
    ) -> Optional[CorporateActionContract]:
        """Returns the latest revision of this action legally visible at as_of, or None."""
        key = (symbol, ex_date, action_type)
        valid = [a for a in self._store.get(key, []) if a.available_at <= as_of]
        return valid[-1] if valid else None

    def query_pit_range(
        self, symbol: str, start_date: str, end_date: str, as_of: datetime
    ) -> List[CorporateActionContract]:
        """Returns the PIT-correct (latest-visible-as-of) revision of every action for `symbol`
        whose ex_date falls within [start_date, end_date]. Actions not yet available_at <= as_of
        are excluded entirely, even if their ex_date falls inside the window."""
        results: List[CorporateActionContract] = []
        for key, revisions in self._store.items():
            k_symbol, k_ex_date, _ = key
            if k_symbol != symbol or not (start_date <= k_ex_date <= end_date):
                continue
            valid = [a for a in revisions if a.available_at <= as_of]
            if valid:
                results.append(valid[-1])
        results.sort(key=lambda a: a.ex_date)
        return results

    def get_history(self, symbol: str, ex_date: str, action_type: str) -> List[CorporateActionContract]:
        """Returns the full immutable chronological revision history for one action key."""
        return list(self._store.get((symbol, ex_date, action_type), []))

    def clear(self):
        self._store.clear()
