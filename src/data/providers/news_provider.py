"""
news_provider.py — News / Company Announcement Provider Adapters.

Mirrors akshare_provider.py's established split: `SyntheticNewsAnnouncementProvider` is a
deterministic, no-network fixture (data_origin="SYNTHETIC_DATA"); `LiveNewsAnnouncementProvider`
explicitly refuses to fetch anything, per the directive's own prohibition ("不要直接接入未经审计的
第三方 News API") — this is a deliberate refusal, not an unimplemented stub, matching
LiveAkShareProviderAdapter.fetch_fundamental_data's exact precedent (see that file).

`_parse_raw_item()` is the Adapter->Contract parsing boundary: it takes a raw, untrusted
dict (the shape a real provider's JSON response would have) and either returns a valid
NewsAnnouncementContract or raises — never silently drops or guesses a missing/malformed field.
This is what "malformed response" / "missing field" / "wrong datatype" / "future timestamp"
mean concretely in this codebase, testable without a live network call.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.data.providers.base import NewsAnnouncementProvider, NewsAnnouncementPage, ProviderError
from src.data.contracts.news_announcement import NewsAnnouncementContract

REQUIRED_RAW_FIELDS = ("source_id", "source", "item_type", "symbols", "title", "published_at")
ITEMS_PER_PAGE = 2

# A special symbol that deterministically triggers a simulated provider outage, mirroring this
# project's existing convention (test fixtures use a dedicated sentinel, not random failure
# injection) for exercising the "provider error" path without a live network dependency.
PROVIDER_ERROR_SIMULATION_SYMBOL = "ERROR_SIM.SH"


def _parse_timestamp(raw_value: Any, field_name: str, source_id: str) -> datetime:
    if raw_value is None:
        raise ValueError(f"FAIL CLOSED: missing required timestamp field '{field_name}' for item '{source_id}'.")
    if isinstance(raw_value, datetime):
        return raw_value
    if not isinstance(raw_value, str):
        raise ValueError(
            f"FAIL CLOSED: wrong datatype for '{field_name}' on item '{source_id}' "
            f"(expected ISO-8601 string or datetime, got {type(raw_value).__name__})."
        )
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError as e:
        raise ValueError(
            f"FAIL CLOSED: malformed timestamp '{raw_value}' for field '{field_name}' on item "
            f"'{source_id}': {e}"
        ) from e


def _parse_raw_item(raw: Dict[str, Any], requested_symbol: str) -> NewsAnnouncementContract:
    """The Adapter -> Contract boundary. `raw` simulates an untrusted provider payload — every
    field is checked before a NewsAnnouncementContract is ever constructed."""
    if not isinstance(raw, dict):
        raise ValueError(f"FAIL CLOSED: malformed provider response item (expected dict, got {type(raw).__name__}).")

    missing = [f for f in REQUIRED_RAW_FIELDS if f not in raw or raw[f] in (None, "")]
    if missing:
        raise ValueError(f"FAIL CLOSED: provider response missing required field(s) {missing}.")

    source_id = raw["source_id"]
    if not isinstance(source_id, str):
        raise ValueError(f"FAIL CLOSED: wrong datatype for 'source_id' (expected str, got {type(source_id).__name__}).")

    symbols = raw["symbols"]
    if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
        raise ValueError(f"FAIL CLOSED: wrong datatype for 'symbols' on item '{source_id}' (expected List[str]).")
    if requested_symbol not in symbols:
        raise ValueError(
            f"FAIL CLOSED: symbol mismatch — item '{source_id}' does not mention requested "
            f"symbol '{requested_symbol}' (mentions {symbols}); refusing to attribute it."
        )

    published_at = _parse_timestamp(raw.get("published_at"), "published_at", source_id)
    available_at = _parse_timestamp(raw["available_at"], "available_at", source_id) if raw.get("available_at") else None
    received_at = _parse_timestamp(raw["received_at"], "received_at", source_id) if raw.get("received_at") else None
    retrieved_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if published_at > retrieved_at:
        raise ValueError(
            f"FAIL CLOSED: item '{source_id}' has published_at ({published_at.isoformat()}) in the "
            f"future relative to retrieved_at ({retrieved_at.isoformat()}) — refusing to trust a "
            "provider timestamp that could not physically have occurred yet."
        )

    return NewsAnnouncementContract(
        source_id=source_id,
        source=raw["source"],
        item_type=raw["item_type"],
        symbols=symbols,
        title=raw["title"],
        body_summary=raw.get("body_summary", ""),
        source_url=raw.get("source_url"),
        published_at=published_at,
        available_at=available_at,
        received_at=received_at,
        retrieved_at=retrieved_at,
        relevance_score=1.0 if requested_symbol in symbols else 0.0,
        quality_status="VALID",
        data_origin=raw.get("data_origin", "SYNTHETIC_DATA"),
    )


class SyntheticNewsAnnouncementProvider(NewsAnnouncementProvider):
    """SYNTHETIC FIXTURE adapter. Deterministic, hardcoded, no network access. Every returned
    contract carries data_origin="SYNTHETIC_DATA" unless the caller explicitly seeds otherwise
    via `seed_items` (tests only) — mirrors AkShareProviderAdapter's exact convention."""

    def __init__(self):
        self._raw_items_by_symbol: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def provider_id(self) -> str:
        return "synthetic_news_primary"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    def seed_items(self, symbol: str, raw_items: List[Dict[str, Any]]) -> None:
        """Test/fixture-only hook: registers raw (unparsed, potentially malformed) item dicts
        for a symbol, exactly as a real provider's JSON response would arrive."""
        self._raw_items_by_symbol.setdefault(symbol, []).extend(raw_items)

    def fetch_news_announcements(
        self, symbol: str, start_date: str, end_date: str, page: int = 1
    ) -> NewsAnnouncementPage:
        if symbol == PROVIDER_ERROR_SIMULATION_SYMBOL:
            raise ProviderError(self.provider_id, f"simulated provider outage for {symbol}.")

        raw_items = self._raw_items_by_symbol.get(symbol, [])
        in_range = [
            r for r in raw_items
            if isinstance(r, dict) and start_date <= str(r.get("announcement_date", r.get("published_at", "")))[:10] <= end_date
        ]

        start = (page - 1) * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_raw = in_range[start:end]
        has_more = end < len(in_range)

        parsed = [_parse_raw_item(r, symbol) for r in page_raw]
        return NewsAnnouncementPage(items=parsed, has_more=has_more, page_number=page)


class LiveNewsAnnouncementProvider(NewsAnnouncementProvider):
    """No audited, live news API is integrated in this codebase. This class exists only to make
    the refusal explicit and discoverable (same precedent as
    LiveAkShareProviderAdapter.fetch_fundamental_data) — never a silent stub, never a fallback
    to synthetic data disguised as real. See AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md
    §10 risk #1."""

    @property
    def provider_id(self) -> str:
        return "live_news_primary"

    @property
    def provider_version(self) -> str:
        return "0.0.0-unimplemented"

    def fetch_news_announcements(
        self, symbol: str, start_date: str, end_date: str, page: int = 1
    ) -> NewsAnnouncementPage:
        raise ProviderError(
            self.provider_id,
            "LiveNewsAnnouncementProvider.fetch_news_announcements is not implemented — no "
            "audited, live news/announcement API is integrated in this codebase. Wiring a real "
            "provider is explicitly out of scope for this directive.",
        )
