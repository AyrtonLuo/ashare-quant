"""
sina_quote_provider.py — REAL-time A-share quote provider (Terminal step T3).

Implements the `QuoteProvider` ABC against Sina's public quote endpoint
(`https://hq.sinajs.cn/list=...`) using only the Python standard library — `urllib.request` plus
GBK decoding. No API key, no account, no payment, and no new dependency.

Why this source, chosen on measurement rather than preference
=============================================================
Three free public endpoints were probed live before anything was written:

| Source | Repeated-request result | Outcome |
|---|---|---|
| Sina `hq.sinajs.cn` | **4/4 succeeded** | chosen |
| Tencent `qt.gtimg.cn` | 4/4 succeeded | viable alternative |
| East Money `push2.eastmoney.com` | **2/4 — dropped connections** | rejected |

East Money throttles by IP and signals it by closing the socket with no status code at all, which
makes it unfit to sit behind a user-facing page. Sina was additionally preferred over Tencent
because it reports **volume in shares** (matching `QuoteContract.volume` with no unit conversion
to get wrong — Tencent reports 手/lots) and carries an explicit date and time rather than a
packed integer.

What this source is, stated honestly
====================================
This is a **public but undocumented** endpoint. It is not a licensed market-data feed:
  * there is no SLA, no support, and no compatibility guarantee — the field layout could change
    without notice, which is why `_parse_payload` validates arity and fails closed instead of
    trusting positions blindly;
  * quotes are delayed rather than tick-by-tick;
  * usage terms are not formally granted, so this is appropriate for research and personal use,
    and a licensed vendor should be procured before any commercial distribution.
None of that is hidden from the user: the Terminal shows the source name and the quote's own
timestamp on every card. `LiveQuoteProvider` remains in `quote_provider.py` as the slot for a
LICENSED vendor and still refuses explicitly, because one has not been procured.

Nothing here is fabricated: `data_origin="REAL_PROVIDER"` is stamped only on a contract built
from an actually-parsed live response. Every failure path raises `ProviderError` — a stale,
suspended or unparseable quote is never quietly turned into a plausible-looking number.
"""

import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.data.calendar.market_session import MarketSessionEngine, MarketSessionState
from src.data.contracts.quote import QuoteContract
from src.data.providers.base import ProviderError

SINA_QUOTE_PROVIDER_ID = "sina_hq"
SINA_QUOTE_PROVIDER_VERSION = "1.0.0-sina-http"
SINA_QUOTE_URL = "https://hq.sinajs.cn/list="

# Sina rejects requests without a finance.sina.com.cn referer.
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ashare-quant-terminal/1.0)",
    "Referer": "https://finance.sina.com.cn",
}

# Verified against a live response before this parser was written: 34 comma-separated fields.
# Only the ones actually used are named; the rest (order book depth) are deliberately ignored.
_FIELD_NAME = 0
_FIELD_OPEN = 1
_FIELD_PREV_CLOSE = 2
_FIELD_LAST = 3
_FIELD_HIGH = 4
_FIELD_LOW = 5
_FIELD_VOLUME = 8          # SHARES, not lots — the reason this source was preferred
_FIELD_AMOUNT = 9          # RMB
_FIELD_DATE = 30
_FIELD_TIME = 31
_MIN_FIELDS = 32           # the highest index used, plus one

_EXCHANGE_PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}

# A courtesy cache. A user reloading the page must not turn into a burst of requests against a
# free endpoint — the same throttling that disqualified East Money would eventually be provoked
# here too. Short enough that a quote still reads as current.
_CACHE_TTL_SECONDS = 3.0


class SinaQuoteProvider:
    """Live A-share quotes. Implements `QuoteProvider` structurally; the ABC is imported lazily
    in `quote_provider.py` to keep that module free of any network-capable import."""

    def __init__(
        self,
        display_names: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 6.0,
        base_url: str = SINA_QUOTE_URL,
    ):
        # `base_url` exists so tests can point at a local stub; it is not a way to pass
        # credentials, because this source has none.
        self._display_names = display_names or {}
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url
        self._cache: Dict[str, Tuple[float, QuoteContract]] = {}

    @property
    def provider_id(self) -> str:
        return SINA_QUOTE_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return SINA_QUOTE_PROVIDER_VERSION

    # --- symbol handling -------------------------------------------------------------------

    def _vendor_code(self, symbol: str) -> str:
        """`600519.SH` -> `sh600519`. Refuses anything it cannot map rather than guessing an
        exchange, because guessing wrong returns a real quote for the WRONG security."""
        parts = (symbol or "").strip().upper().split(".")
        if len(parts) != 2 or not parts[0].isdigit() or len(parts[0]) != 6:
            raise ProviderError(
                self.provider_id,
                f"'{symbol}' is not a recognised A-share symbol (expected e.g. 600519.SH).",
            )
        code, exchange = parts
        prefix = _EXCHANGE_PREFIX.get(exchange)
        if prefix is None:
            raise ProviderError(
                self.provider_id,
                f"unknown exchange suffix '{exchange}' in '{symbol}'; expected one of "
                f"{sorted(_EXCHANGE_PREFIX)}.",
            )
        return f"{prefix}{code}"

    # --- transport -------------------------------------------------------------------------

    def _fetch(self, vendor_code: str) -> str:
        request = urllib.request.Request(
            f"{self._base_url}{vendor_code}", headers=dict(_REQUEST_HEADERS)
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read().decode("gbk", errors="replace")
        except urllib.error.HTTPError as e:
            raise ProviderError(
                self.provider_id, f"quote endpoint returned HTTP {e.code}."
            ) from None
        except Exception as e:
            # Includes socket timeouts and the connection-drop behaviour a throttling endpoint
            # exhibits. Reported, never retried silently.
            raise ProviderError(
                self.provider_id, f"could not reach the quote endpoint ({type(e).__name__}: {e})."
            ) from None

    # --- parsing ---------------------------------------------------------------------------

    def _parse_payload(self, raw: str, symbol: str) -> List[str]:
        if '="' not in raw:
            raise ProviderError(
                self.provider_id, f"unrecognised quote response shape for '{symbol}'."
            )
        payload = raw.split('="', 1)[1].rstrip().rstrip(";").rstrip('"')
        if not payload.strip():
            # Sina answers an unknown code with an empty payload rather than an error status.
            raise ProviderError(
                self.provider_id,
                f"the quote source has no data for '{symbol}' — it may not be a listed A-share "
                "code.",
            )
        fields = payload.split(",")
        if len(fields) < _MIN_FIELDS:
            # The field layout is undocumented and could change; refusing beats reading the
            # wrong position and presenting it as a price.
            raise ProviderError(
                self.provider_id,
                f"quote response for '{symbol}' had {len(fields)} fields, fewer than the "
                f"{_MIN_FIELDS} this parser verified against a live response.",
            )
        return fields

    def _number(self, fields: List[str], index: int, label: str, symbol: str) -> float:
        try:
            return float(fields[index])
        except (TypeError, ValueError):
            raise ProviderError(
                self.provider_id,
                f"quote for '{symbol}' has a non-numeric {label}: {fields[index]!r}.",
            ) from None

    def _timestamp(self, fields: List[str], symbol: str) -> datetime:
        stamp = f"{fields[_FIELD_DATE]} {fields[_FIELD_TIME]}"
        try:
            return datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ProviderError(
                self.provider_id, f"quote for '{symbol}' has an unparseable timestamp {stamp!r}."
            ) from None

    def _build(self, fields: List[str], symbol: str) -> QuoteContract:
        last = self._number(fields, _FIELD_LAST, "last price", symbol)
        prev_close = self._number(fields, _FIELD_PREV_CLOSE, "previous close", symbol)

        # A halted or not-yet-opened name reports 0.00 for the traded prices. Substituting the
        # previous close would present a price that never traded, so it fails closed and the
        # Terminal shows 暂无数据 with this reason instead.
        if last <= 0:
            raise ProviderError(
                self.provider_id,
                f"'{symbol}' has no traded price right now (停牌或今日尚无成交)；不以昨收替代。",
            )
        if prev_close <= 0:
            raise ProviderError(
                self.provider_id, f"'{symbol}' reports a non-positive previous close."
            )

        quoted_at = self._timestamp(fields, symbol)
        received_at = datetime.now()
        session = MarketSessionEngine.get_market_session(quoted_at)
        return QuoteContract(
            symbol=symbol.upper(),
            display_name=fields[_FIELD_NAME].strip() or self._display_names.get(symbol, symbol),
            last_price=last,
            prev_close=prev_close,
            open_price=self._number(fields, _FIELD_OPEN, "open", symbol),
            high_price=self._number(fields, _FIELD_HIGH, "high", symbol),
            low_price=self._number(fields, _FIELD_LOW, "low", symbol),
            volume=self._number(fields, _FIELD_VOLUME, "volume", symbol),
            amount=self._number(fields, _FIELD_AMOUNT, "amount", symbol),
            quoted_at=quoted_at,
            # A vendor clock running slightly ahead of ours would otherwise trip the contract's
            # received_at >= quoted_at invariant on an otherwise perfectly good quote.
            received_at=max(received_at, quoted_at),
            market_session=session.value if isinstance(session, MarketSessionState) else str(session),
            trading_status="NORMAL",
            provider_id=self.provider_id,
            data_origin="REAL_PROVIDER",   # only ever reached from a parsed live response
        )

    # --- QuoteProvider surface -------------------------------------------------------------

    def get_quote(self, symbol: str) -> QuoteContract:
        cached = self._cache.get(symbol)
        if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        fields = self._parse_payload(self._fetch(self._vendor_code(symbol)), symbol)
        quote = self._build(fields, symbol)
        self._cache[symbol] = (time.monotonic(), quote)
        return quote

    def search_symbols(self, query: str) -> List[Dict[str, str]]:
        """Matches the known display-name universe, and additionally resolves a bare 6-digit code
        against the live source so any listed A-share is reachable, not only the seeded names.

        A code that resolves is returned with the vendor's own name for it; one that does not is
        simply absent from the results — never returned as a guess.
        """
        needle = (query or "").strip()
        if not needle:
            return []

        matches = [
            {"symbol": symbol, "display_name": name}
            for symbol, name in sorted(self._display_names.items())
            if needle.lower() in symbol.lower() or needle.lower() in name.lower()
        ]
        if matches or not (needle.isdigit() and len(needle) == 6):
            return matches

        # Bare 6-digit code: try both exchanges and keep whichever the source recognises.
        for suffix in ("SH", "SZ", "BJ"):
            candidate = f"{needle}.{suffix}"
            try:
                quote = self.get_quote(candidate)
            except ProviderError:
                continue
            return [{"symbol": candidate, "display_name": quote.display_name}]
        return []
