"""
quote_provider.py — QuoteProvider ABC and its two implementations.

Terminal directive step T1. Mirrors the established provider pattern exactly
(`UnifiedDataProvider`, `NewsAnnouncementProvider`): a `provider_id`/`provider_version` property
pair plus abstract methods, so a real vendor can be added later by implementing this same ABC
without changing anything upstream.

Two implementations ship here, and the split is the same one this codebase already uses for news:

- `GoldenQuoteProvider` — derives a quote from the certified GOLDEN_DATASET so the Terminal can
  be built and demonstrated today. Every quote it returns is stamped `data_origin
  ="GOLDEN_DATASET"`, which the Terminal renders as an unmissable DEMO DATA badge. It is
  **structurally incapable** of producing `REAL_PROVIDER` — the value is hard-coded, not a
  parameter.
- `LiveQuoteProvider` — the real-vendor slot. It **refuses explicitly** rather than pretending,
  exactly as `LiveNewsAnnouncementProvider` does, because no market-data vendor has been chosen
  or paid for (CEO decision, deferred). It exists so the interface is real and the gap is
  visible in code rather than only in a document.

No network call is made from this module, and no dependency is added.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from src.data.calendar.market_session import MarketSessionEngine, MarketSessionState
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.quote import QuoteContract
from src.data.providers.base import ProviderError

GOLDEN_QUOTE_PROVIDER_ID = "golden_demo_quote"
LIVE_QUOTE_PROVIDER_ID = "live_quote"

# Why a real quote provider does not exist yet. Surfaced as a constant so the UI and the tests
# quote the same reason, and so it reads as a deliberate state rather than an oversight.
NO_QUOTE_VENDOR_REASON = (
    "QUOTE_PROVIDER_NOT_CONFIGURED: no real-time market-data vendor has been selected or "
    "provisioned. A-share real-time quotes are a licensed product; the vendor and cost decision "
    "is pending. Until then the Terminal shows clearly-labelled DEMO DATA, never a fabricated "
    "live price."
)


class QuoteProvider(ABC):
    """One quote for one symbol, as of now. Deliberately NOT keyed by trade_date — that is the
    research path's shape (`UnifiedDataProvider.fetch_market_data`), and conflating the two is
    what would let a historical bar be presented as a live price."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def provider_version(self) -> str: ...

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteContract:
        """Must raise ProviderError on any failure — never return a partial or guessed quote,
        never substitute a stale value silently."""
        ...

    @abstractmethod
    def search_symbols(self, query: str) -> List[Dict[str, str]]:
        """Powers the Terminal's search box. Returns [{"symbol", "display_name"}]; an empty list
        means no match, which is a valid answer and not an error."""
        ...


class GoldenQuoteProvider(QuoteProvider):
    """DEMO provider. Derives a quote from the certified GOLDEN_DATASET's last available bar.

    Honest about what it is, in three ways that cannot be switched off:
      * `data_origin` is hard-coded `"GOLDEN_DATASET"` — not a constructor parameter.
      * `quoted_at` is the golden bar's OWN trading date, not `datetime.now()`. A demo quote that
        stamped itself with the current time would look live, which is exactly the deception the
        directive forbids; instead its age is honestly enormous and the UI can say so.
      * `market_session` is resolved from that same historical timestamp, so a demo quote never
        claims the market is open right now.
    """

    def __init__(
        self,
        bars_by_symbol: Dict[str, List[MarketDataContract]],
        display_names: Optional[Dict[str, str]] = None,
    ):
        self._bars = bars_by_symbol
        self._display_names = display_names or {}

    @property
    def provider_id(self) -> str:
        return GOLDEN_QUOTE_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return "1.0.0-golden-demo"

    def search_symbols(self, query: str) -> List[Dict[str, str]]:
        """Matches on symbol or display name, case-insensitively. No fuzzy matching: a search box
        that guesses would be a poor place to be clever about which company the user meant."""
        needle = (query or "").strip().lower()
        if not needle:
            return []
        matches = []
        for symbol in sorted(self._bars):
            display_name = self._display_names.get(symbol, symbol)
            if needle in symbol.lower() or needle in display_name.lower():
                matches.append({"symbol": symbol, "display_name": display_name})
        return matches

    def get_quote(self, symbol: str) -> QuoteContract:
        bars = self._bars.get(symbol)
        if not bars:
            raise ProviderError(
                self.provider_id,
                f"no GOLDEN_DATASET bars available for '{symbol}'; refusing to invent a quote.",
            )

        ordered = sorted(bars, key=lambda b: b.trading_date)
        latest = ordered[-1]
        # With only one bar there is no prior close to measure change against. Using the bar's
        # own open as a stand-in would silently redefine what "涨跌幅" means, so it fails closed.
        if len(ordered) < 2:
            raise ProviderError(
                self.provider_id,
                f"only one bar available for '{symbol}'; a quote needs a previous close to "
                "report change, and substituting the open would misstate it.",
            )
        previous = ordered[-2]

        quoted_at = latest.timestamp
        session = MarketSessionEngine.get_market_session(quoted_at)
        return QuoteContract(
            symbol=symbol,
            display_name=self._display_names.get(symbol, symbol),
            last_price=latest.close_price,
            prev_close=previous.close_price,
            open_price=latest.open_price,
            high_price=latest.high_price,
            low_price=latest.low_price,
            volume=latest.volume,
            amount=latest.amount,
            quoted_at=quoted_at,
            received_at=max(datetime.now(), quoted_at),
            market_session=session.value if isinstance(session, MarketSessionState) else str(session),
            trading_status=latest.trading_status,
            provider_id=self.provider_id,
            data_origin="GOLDEN_DATASET",   # hard-coded: this provider can never claim REAL
        )


class LiveQuoteProvider(QuoteProvider):
    """The real-vendor slot. Refuses explicitly until a vendor is chosen and provisioned.

    This class is not a placeholder to be quietly filled with a fake later: it raises so that any
    attempt to obtain a real quote fails loudly and visibly, rather than falling back to demo
    data wearing a live badge.
    """

    @property
    def provider_id(self) -> str:
        return LIVE_QUOTE_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return "0.0.0-not-configured"

    def search_symbols(self, query: str) -> List[Dict[str, str]]:
        raise ProviderError(self.provider_id, NO_QUOTE_VENDOR_REASON)

    def get_quote(self, symbol: str) -> QuoteContract:
        raise ProviderError(self.provider_id, NO_QUOTE_VENDOR_REASON)
