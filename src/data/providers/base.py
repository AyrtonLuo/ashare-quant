"""
base.py — Unified Data Provider Abstract Interface & Provider Error definitions.
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List, Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.contracts.news_announcement import NewsAnnouncementContract


class ProviderError(Exception):
    """Base exception for data provider timeouts, rate limits, and schema changes."""
    def __init__(self, provider_id: str, error_message: str):
        self.provider_id = provider_id
        self.error_message = error_message
        super().__init__(f"[{provider_id}] Provider Error: {error_message}")


class UnifiedDataProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: pass

    @property
    @abstractmethod
    def provider_version(self) -> str: pass

    @abstractmethod
    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        """Fetches daily bar market data adapted into MarketDataContract."""
        pass

    @abstractmethod
    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        """Fetches point-in-time fundamental statement adapted into FundamentalDataContract."""
        pass

    @abstractmethod
    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> List[CorporateActionContract]:
        """Fetches corporate action events."""
        pass


@dataclass(frozen=True)
class NewsAnnouncementPage:
    """One page of a paginated news/announcement fetch. Partial provider failure is a first-
    class, visible outcome — never silently swallowed into an empty-looking success. AI_QUANT_
    RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §3, directive item 4 ("pagination", "partial
    provider failure")."""
    items: List[NewsAnnouncementContract] = field(default_factory=list)
    has_more: bool = False
    page_number: int = 1
    partial_failure: bool = False       # True if this page's fetch itself only partially
                                         # succeeded (e.g. provider returned a truncated payload)
    partial_failure_reason: Optional[str] = None


class NewsAnnouncementProvider(ABC):
    """A separate ABC from UnifiedDataProvider — deliberately not added as a new abstract method
    on UnifiedDataProvider, which would force every existing concrete provider (TuShareAdapter,
    AkShareProviderAdapter, and their Live* variants) to implement an unrelated method. Same
    provider_id/provider_version pattern, so the two ABCs remain structurally consistent."""

    @property
    @abstractmethod
    def provider_id(self) -> str: pass

    @property
    @abstractmethod
    def provider_version(self) -> str: pass

    @abstractmethod
    def fetch_news_announcements(
        self, symbol: str, start_date: str, end_date: str, page: int = 1
    ) -> NewsAnnouncementPage:
        """Fetches one page of news/announcements for `symbol` within [start_date, end_date].
        Callers must loop while `has_more` is True to retrieve every page — see the adapter's
        own docstring for how partial-page failures during that loop must be surfaced, never
        silently dropped."""
        pass
