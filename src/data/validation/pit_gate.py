"""
pit_gate.py — Point-in-Time (PIT) Protection Gatekeeper for Backtesting & Analysis.
"""

from datetime import datetime
from typing import List
from src.data.contracts.temporal import TemporalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.news_announcement import NewsAnnouncementContract


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
        """Returns only corporate actions legally known at as_of_cutoff time: both available_at
        (disclosure/ingestion visibility) AND received_at (system ingestion time) must be set
        and <= as_of_cutoff — matching filter_pit_fundamentals()'s dual-cutoff contract, closing
        a gap where corporate actions previously checked available_at only. Never filtered on
        ex_date/effective_date — an action's economic effective date and its PIT availability
        are separate concepts. A received_at left unset (None) is excluded rather than treated
        as always-available."""
        return [
            a for a in actions
            if a.received_at is not None
            and a.available_at <= as_of_cutoff and a.received_at <= as_of_cutoff
        ]

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

    @staticmethod
    def filter_pit_news_announcements(
        items: List[NewsAnnouncementContract], as_of_cutoff: datetime
    ) -> List[NewsAnnouncementContract]:
        """AI_QUANT_RESEARCH_ANALYST — extends this same dual-cutoff PIT pattern to news/company
        announcements, per the directive's explicit rule: published_at <= as_of AND received_at
        <= as_of. Uses `published_at` (not `available_at`) as the CEO directive literally
        specifies — for news, publication IS the moment of legal citability (unlike a corporate
        action, where an economic effective date and its legal disclosure date can genuinely
        differ). `available_at` remains on the contract as a descriptive field for cases where
        legal availability differs from publication (e.g. an embargo), but is deliberately not
        part of THIS gate's check, to match the directive's formula exactly rather than silently
        inventing a third condition. Either timestamp left unset (None) excludes the item —
        an unknown timestamp can never satisfy a PIT check, matching every other filter here."""
        return [
            i for i in items
            if i.published_at is not None and i.received_at is not None
            and i.published_at <= as_of_cutoff and i.received_at <= as_of_cutoff
        ]
