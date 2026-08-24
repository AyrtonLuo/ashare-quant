"""
tencent_history_provider.py — REAL daily K-line history (Terminal step T3.5).

Implements `MarketHistoryProvider` against Tencent's public K-line endpoint
(`web.ifzq.gtimg.cn/appstock/app/fqkline/get`) using only the standard library. No API key, no
account, no payment, no new dependency.

Why this source, decided on measurement and data quality rather than preference
===============================================================================
Three free endpoints were probed live before anything was written:

| Source | Repeated requests | Adjustment | Outcome |
|---|---|---|---|
| Tencent `web.ifzq.gtimg.cn` | **4/4** | **forward-adjusted (qfq)** | chosen |
| Sina `getKLineData` | 4/4 | **unadjusted (raw)** | rejected — see below |
| East Money `push2his` | **3/4 — dropped socket** | n/a | rejected |

Sina was rejected on DATA QUALITY, not availability. Its series is unadjusted, and 600519 has a
corporate action inside the current 120-day window: Sina reports 1326.000 for 2026-05-29 where
the adjusted series reports 1297.976. Computing MA/RSI/MACD across that gap produces a visible
step that is an artefact of the dividend, not of the market — indicators would be plainly wrong
for a stock the Terminal actually lists. East Money again closed connections without a status
code, and its documented field flags returned negative prices.

The row layout `[date, open, close, high, low, volume]` is POSITIONAL and undocumented — note
that open and close are adjacent and easy to transpose. It was therefore verified empirically
across 105 bars whose four prices were all distinct, asserting high == max and low == min, before
this parser was written; `_parse_row` re-asserts those invariants on every row at runtime.

Honest limitations, stated rather than discovered later
=======================================================
- **The prices are vendor forward-adjusted (qfq), NOT point-in-time.** They are re-adjusted
  whenever a new corporate action occurs, so a series fetched today differs from the same series
  fetched last year. That is correct for displaying current technical indicators and WRONG for
  backtesting. `input_price_basis` reports `VENDOR_FORWARD_ADJUSTED` so nothing downstream can
  mistake it for the PIT-adjusted series the research core uses. This provider is deliberately
  not reachable from any certified research path.
- **Volume is reported in 手 (lots) and converted to shares by x100.** The vendor rounds lots to
  three decimals, so converted share counts carry ~0.001% rounding (e.g. 33472.000 lots ->
  3,347,200 against an exact 3,347,231). Immaterial for a volume ratio; disclosed anyway.
- Public but **undocumented and unlicensed**: no SLA, no compatibility guarantee. Fine for
  research and personal use; a licensed vendor is warranted before commercial distribution.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Tuple

from src.data.contracts.market_data import MarketDataContract
from src.data.providers.base import ProviderError
from src.data.providers.history_provider import MarketHistoryProvider

TENCENT_HISTORY_PROVIDER_ID = "tencent_kline"
TENCENT_HISTORY_PROVIDER_VERSION = "1.0.0-tencent-http"
TENCENT_HISTORY_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# Verified across 105 distinct-price bars before this parser existed.
_ROW_DATE, _ROW_OPEN, _ROW_CLOSE, _ROW_HIGH, _ROW_LOW, _ROW_VOLUME = 0, 1, 2, 3, 4, 5
_ROW_MIN_WIDTH = 6

_SHARES_PER_LOT = 100.0
_EXCHANGE_PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
_CACHE_TTL_SECONDS = 60.0   # daily bars change once a day; a minute is generous


class TencentHistoryProvider(MarketHistoryProvider):
    def __init__(self, timeout_seconds: float = 8.0, base_url: str = TENCENT_HISTORY_URL):
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url
        self._cache: Dict[Tuple[str, int], Tuple[float, List[MarketDataContract]]] = {}

    @property
    def provider_id(self) -> str:
        return TENCENT_HISTORY_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return TENCENT_HISTORY_PROVIDER_VERSION

    @property
    def input_price_basis(self) -> str:
        return "VENDOR_FORWARD_ADJUSTED"

    def _vendor_code(self, symbol: str) -> str:
        parts = (symbol or "").strip().upper().split(".")
        if len(parts) != 2 or not parts[0].isdigit() or len(parts[0]) != 6:
            raise ProviderError(
                self.provider_id,
                f"'{symbol}' is not a recognised A-share symbol (expected e.g. 600519.SH).",
            )
        prefix = _EXCHANGE_PREFIX.get(parts[1])
        if prefix is None:
            raise ProviderError(
                self.provider_id, f"unknown exchange suffix '{parts[1]}' in '{symbol}'."
            )
        return f"{prefix}{parts[0]}"

    def _fetch(self, vendor_code: str, limit: int) -> dict:
        url = f"{self._base_url}?param={vendor_code},day,,,{limit},qfq"
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ashare-quant-terminal/1.0)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise ProviderError(
                self.provider_id, f"history endpoint returned HTTP {e.code}."
            ) from None
        except Exception as e:
            raise ProviderError(
                self.provider_id,
                f"could not reach the history endpoint ({type(e).__name__}: {e}).",
            ) from None

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ProviderError(
                self.provider_id, f"history response is not valid JSON ({e})."
            ) from None
        if not isinstance(payload, dict):
            raise ProviderError(self.provider_id, "history response is not a JSON object.")
        return payload

    def _rows(self, payload: dict, vendor_code: str, symbol: str) -> List[list]:
        if payload.get("code") not in (0, None):
            raise ProviderError(
                self.provider_id,
                f"history endpoint reported code={payload.get('code')} for '{symbol}'.",
            )
        node = (payload.get("data") or {}).get(vendor_code)
        if not isinstance(node, dict):
            raise ProviderError(
                self.provider_id,
                f"the history source has no data for '{symbol}' — it may not be a listed "
                "A-share code.",
            )
        # The adjusted series is the point of using this endpoint. If it is absent, falling back
        # to an unadjusted key would silently change the price basis this provider advertises.
        rows = node.get("qfqday") or node.get("day")
        if node.get("qfqday") is None and rows is not None:
            raise ProviderError(
                self.provider_id,
                f"history for '{symbol}' contains no forward-adjusted series; refusing to "
                "substitute the unadjusted one, which would contradict the declared price basis.",
            )
        if not isinstance(rows, list) or not rows:
            raise ProviderError(
                self.provider_id, f"history for '{symbol}' contains no bars."
            )
        return rows

    def _parse_row(self, row: list, symbol: str) -> MarketDataContract:
        if not isinstance(row, list) or len(row) < _ROW_MIN_WIDTH:
            raise ProviderError(
                self.provider_id,
                f"history row for '{symbol}' has {len(row) if isinstance(row, list) else '?'} "
                f"fields, fewer than the {_ROW_MIN_WIDTH} this parser verified.",
            )
        trading_date = str(row[_ROW_DATE])
        try:
            timestamp = datetime.strptime(trading_date, "%Y-%m-%d").replace(hour=15)
        except ValueError:
            raise ProviderError(
                self.provider_id, f"history row for '{symbol}' has a bad date {trading_date!r}."
            ) from None

        try:
            open_price = float(row[_ROW_OPEN])
            close_price = float(row[_ROW_CLOSE])
            high_price = float(row[_ROW_HIGH])
            low_price = float(row[_ROW_LOW])
            lots = float(row[_ROW_VOLUME])
        except (TypeError, ValueError):
            raise ProviderError(
                self.provider_id,
                f"history row for '{symbol}' on {trading_date} has a non-numeric field.",
            ) from None

        # The layout is positional and undocumented; open and close are adjacent and easy to
        # transpose. These invariants were verified across 105 live bars and are re-checked on
        # every row, so a silent vendor reordering surfaces as a refusal, not as wrong prices.
        if high_price < max(open_price, close_price, low_price) or \
                low_price > min(open_price, close_price, high_price):
            raise ProviderError(
                self.provider_id,
                f"history row for '{symbol}' on {trading_date} violates high/low bounds "
                f"(O={open_price} C={close_price} H={high_price} L={low_price}) — the vendor's "
                "field order may have changed.",
            )
        if close_price <= 0:
            raise ProviderError(
                self.provider_id,
                f"history row for '{symbol}' on {trading_date} has a non-positive close.",
            )

        return MarketDataContract(
            symbol=symbol.upper(), timestamp=timestamp, trading_date=trading_date,
            open_price=open_price, high_price=high_price, low_price=low_price,
            close_price=close_price,
            volume=round(lots * _SHARES_PER_LOT, 4),   # vendor reports 手; see module docstring
            amount=0.0,          # this endpoint does not report turnover; never invented
            adj_factor=1.0,      # the series is already vendor-adjusted, so no further factor
            unadjusted_close=close_price,
            trading_status="NORMAL", quality_status="VALID",
            data_origin="REAL_PROVIDER",
        )

    def get_daily_bars(self, symbol: str, limit: int = 120) -> List[MarketDataContract]:
        if limit <= 0:
            raise ProviderError(self.provider_id, f"invalid bar limit {limit}.")
        cache_key = (symbol, limit)
        cached = self._cache.get(cache_key)
        if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        vendor_code = self._vendor_code(symbol)
        rows = self._rows(self._fetch(vendor_code, limit), vendor_code, symbol)
        bars = [self._parse_row(row, symbol) for row in rows]
        bars.sort(key=lambda b: b.trading_date)
        self._cache[cache_key] = (time.monotonic(), bars)
        return bars
