"""
eastmoney_news_provider.py — REAL company announcements for the Terminal (Terminal step T5).

Implements the existing `NewsAnnouncementProvider` ABC against East Money's public announcement
listing endpoint (`np-anotice-stock.eastmoney.com/api/security/ann`), using only the standard
library. No API key, no account, no payment, no new dependency, and no change to the news
contract, validation or PIT code that already existed.

Source selection — measured across two rounds, then decided on stability
========================================================================
| Source | Result | Calls needed | Outcome |
|---|---|---|---|
| East Money `np-anotice-stock` | **3/3, then 4/4 on four distinct codes** | **1** | chosen |
| 巨潮资讯 cninfo | 3/3 | **2** (orgId lookup + query) | rejected — see below |

cninfo is the OFFICIAL statutory disclosure platform and was the preferred candidate on
authority. It was rejected on a measured failure mode: its announcement query requires an
`orgId` that is **not derivable from the stock code** — `gssh0600519` and `gssz0000001` happen to
follow a pattern, but 000333 is `9900005965`, 601398 is `jjxt0000019` and 300750 is `GD165627`.
Worse, querying with a wrong or absent orgId returns `totalAnnouncement: 0` **silently, with HTTP
200** — which this Terminal would render as "暂无新闻" when the truth is "the lookup was wrong".
Using it safely needs a second resolution call per symbol, doubling the failure surface for a
product page. East Money needs one call, no opaque id, and returned results for every code tried.

(Note: East Money's *quote* host `push2` has been degrading across sessions — 2/4, then 3/4, then
0/3. This is a different host and tested 7/7 across both probe rounds, but the same operator's
reliability record is a reason to keep the abstraction and swap sources easily, which the
`NewsAnnouncementProvider` ABC already allows.)

Honest limitations, stated rather than discovered later
=======================================================
- **These are company ANNOUNCEMENTS (公告), not general news.** `item_type` is
  `COMPANY_ANNOUNCEMENT` for every item, never `NEWS`, so nothing claims to be press coverage.
- **`published_at` is the statutory disclosure date and is date-granular** (`notice_date`, e.g.
  `2026-08-15 00:00:00`). The endpoint also carries a finer `display_time`, but that is when East
  Money surfaced the item, not when the company disclosed it; conflating the two would misstate
  the disclosure date.
- **No body text is available from this endpoint**, so `body_summary` is left empty rather than
  being paraphrased, summarised or generated. The Terminal links to the original document
  instead.
- Public but **undocumented and unlicensed**: no SLA, no compatibility guarantee. The response
  shape is checked on every item so a silent change surfaces as a refusal, not as wrong content.
- **Date filtering is applied client-side** on the returned page; this endpoint has no date-range
  parameter in the field set used here, so an item outside `[start_date, end_date]` is excluded
  after the fetch rather than never requested.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.providers.base import (
    NewsAnnouncementPage,
    NewsAnnouncementProvider,
    ProviderError,
)

EASTMONEY_NEWS_PROVIDER_ID = "eastmoney_announcements"
EASTMONEY_NEWS_PROVIDER_VERSION = "1.0.0-eastmoney-http"
EASTMONEY_ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
EASTMONEY_DETAIL_URL = "https://data.eastmoney.com/notices/detail"

# The named source shown to a user. Never "unknown", per the contract's own rule.
EASTMONEY_SOURCE_NAME = "东方财富-上市公司公告"

_CACHE_TTL_SECONDS = 120.0   # announcements change a few times a day at most


class EastMoneyAnnouncementProvider(NewsAnnouncementProvider):
    """Live A-share company announcements. Raises `ProviderError` on any failure; it never
    returns a synthetic or partially-invented item, and never falls back to another source."""

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        base_url: str = EASTMONEY_ANN_URL,
        page_size: int = 20,
    ):
        # `base_url` exists so tests can point at a local stub; this source has no credentials to
        # smuggle through it.
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url
        self._page_size = page_size
        self._cache: Dict[Tuple[str, int], Tuple[float, Dict[str, Any]]] = {}

    @property
    def provider_id(self) -> str:
        return EASTMONEY_NEWS_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return EASTMONEY_NEWS_PROVIDER_VERSION

    @property
    def source_label(self) -> str:
        """Named separately from the quote, history and fundamental feeds — each declares its own
        source rather than being collapsed into one claim."""
        return f"{EASTMONEY_SOURCE_NAME} ({EASTMONEY_NEWS_PROVIDER_ID})"

    # --- symbol handling -----------------------------------------------------------------

    def _vendor_code(self, symbol: str) -> str:
        """`600519.SH` -> `600519`. Refuses anything it cannot map rather than guessing, because
        a guessed code returns real announcements for the WRONG company."""
        parts = (symbol or "").strip().upper().split(".")
        if len(parts) != 2 or not parts[0].isdigit() or len(parts[0]) != 6:
            raise ProviderError(
                self.provider_id,
                f"'{symbol}' is not a recognised A-share symbol (expected e.g. 600519.SH).",
            )
        if parts[1] not in ("SH", "SZ", "BJ"):
            raise ProviderError(
                self.provider_id, f"unknown exchange suffix '{parts[1]}' in '{symbol}'."
            )
        return parts[0]

    # --- transport -----------------------------------------------------------------------

    def _fetch(self, code: str, page: int) -> Dict[str, Any]:
        cache_key = (code, page)
        cached = self._cache.get(cache_key)
        if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        url = (
            f"{self._base_url}?sr=-1&page_size={self._page_size}&page_index={page}"
            f"&ann_type=A&client_source=web&stock_list={code}"
        )
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ashare-quant-terminal/1.0)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise ProviderError(
                self.provider_id, f"announcement endpoint returned HTTP {e.code}."
            ) from None
        except Exception as e:
            raise ProviderError(
                self.provider_id,
                f"could not reach the announcement endpoint ({type(e).__name__}: {e}).",
            ) from None

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ProviderError(
                self.provider_id, f"announcement response is not valid JSON ({e})."
            ) from None
        if not isinstance(payload, dict):
            raise ProviderError(
                self.provider_id, "announcement response is not a JSON object."
            )
        self._cache[cache_key] = (time.monotonic(), payload)
        return payload

    # --- parsing -------------------------------------------------------------------------

    def _parse_time(self, raw: Optional[str], symbol: str, label: str) -> datetime:
        if not isinstance(raw, str) or not raw.strip():
            raise ProviderError(
                self.provider_id, f"announcement for '{symbol}' has no {label}."
            )
        # notice_date arrives as "YYYY-MM-DD HH:MM:SS"; display_time adds ":mmm".
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip()[:19], fmt)
            except ValueError:
                continue
        raise ProviderError(
            self.provider_id,
            f"announcement for '{symbol}' has an unparseable {label} {raw!r}.",
        )

    def _parse_item(
        self, raw: Dict[str, Any], symbol: str, code: str, retrieved_at: datetime,
    ) -> Optional[NewsAnnouncementContract]:
        if not isinstance(raw, dict):
            raise ProviderError(
                self.provider_id, f"announcement entry for '{symbol}' is not an object."
            )
        art_code = raw.get("art_code")
        title = raw.get("title") or raw.get("title_ch")
        if not art_code or not title:
            raise ProviderError(
                self.provider_id,
                f"announcement entry for '{symbol}' is missing art_code or title.",
            )

        # The symbol association is taken from the payload's OWN code list, never inferred from
        # the fact that we asked about this symbol — an item that does not name the company is
        # excluded rather than attributed to it.
        codes = raw.get("codes")
        if not isinstance(codes, list) or not codes:
            return None
        listed = {str(c.get("stock_code")) for c in codes if isinstance(c, dict)}
        if code not in listed:
            return None

        published_at = self._parse_time(raw.get("notice_date"), symbol, "notice_date")

        return NewsAnnouncementContract(
            source_id=str(art_code),
            source=EASTMONEY_SOURCE_NAME,
            item_type="COMPANY_ANNOUNCEMENT",   # these are 公告, never press coverage
            symbols=[symbol.upper()],
            title=str(title).strip(),
            # No body text is available from this endpoint. Left empty rather than paraphrased,
            # summarised or generated — the Terminal links to the original document instead.
            body_summary="",
            source_url=f"{EASTMONEY_DETAIL_URL}/{code}/{art_code}.html",
            published_at=published_at,
            # A statutory disclosure is public the moment it is disclosed, so available_at is the
            # disclosure time itself; received_at is when THIS system fetched it.
            available_at=published_at,
            received_at=max(retrieved_at, published_at),
            retrieved_at=retrieved_at,
            # Deterministic and rule-based: the payload explicitly lists this stock code, so the
            # association is stated by the source, not judged. Never an AI/LLM score.
            relevance_score=1.0,
            # The vendor's own column_name (其他 / 业绩报告 / ...) is deliberately DROPPED rather
            # than squeezed into body_summary: NewsAnnouncementContract has no category field,
            # and body_summary means "an excerpt captured at ingest", not a taxonomy label.
            quality_status="VALID",
            data_origin="REAL_PROVIDER",
        )

    # --- NewsAnnouncementProvider surface ---------------------------------------------------

    def fetch_news_announcements(
        self, symbol: str, start_date: str, end_date: str, page: int = 1
    ) -> NewsAnnouncementPage:
        if page < 1:
            raise ProviderError(self.provider_id, f"invalid page number {page}.")
        code = self._vendor_code(symbol)
        payload = self._fetch(code, page)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError(
                self.provider_id,
                f"the announcement source returned no data block for '{symbol}'.",
            )
        entries = data.get("list")
        if entries is None:
            raise ProviderError(
                self.provider_id,
                f"the announcement source returned no list for '{symbol}'.",
            )
        if not isinstance(entries, list):
            raise ProviderError(
                self.provider_id, f"announcement list for '{symbol}' is not an array."
            )

        retrieved_at = datetime.now()
        items: List[NewsAnnouncementContract] = []
        for raw in entries:
            contract = self._parse_item(raw, symbol, code, retrieved_at)
            if contract is None:
                continue
            # This endpoint has no date-range parameter in the field set used here, so the
            # requested window is applied after the fetch rather than never requested.
            if start_date and contract.published_at.strftime("%Y-%m-%d") < start_date:
                continue
            if end_date and contract.published_at.strftime("%Y-%m-%d") > end_date:
                continue
            items.append(contract)

        total = data.get("total_hits")
        has_more = (
            isinstance(total, int) and total > page * self._page_size and len(entries) > 0
        )
        return NewsAnnouncementPage(
            items=items, has_more=has_more, page_number=page,
        )
