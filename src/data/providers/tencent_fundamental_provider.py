"""
tencent_fundamental_provider.py — REAL fundamental / valuation data (Terminal step T4).

Implements `FundamentalProvider` against Tencent's public quote endpoint
(`qt.gtimg.cn/q=`), which carries vendor-computed valuation metrics alongside the price. Standard
library only (`urllib` + GBK decoding); no API key, no account, no payment, no new dependency.

Source selection — measured, and one candidate was disqualified by DATA, not availability
==========================================================================================
| Source | Repeated requests | Key needed | Outcome |
|---|---|---|---|
| Tencent `qt.gtimg.cn` | **3/3** | no | chosen |
| Sina `hq.sinajs.cn/list=..._i` | reachable | no | rejected as PRIMARY — see below |
| East Money `push2` | **0/3 — every socket dropped** | no | rejected |

East Money is now refusing every request outright, worse than the 2/4 and 3/4 seen in T3/T3.5.

Every field this provider reports was verified against an INDEPENDENT derivation from Sina's
`_i` (share capital / financials) endpoint, across three symbols including a dual-listed one:

  * `price x totalShares / 1e8 == 总市值` held EXACTLY on 3/3 (600519, 000001, 000333).
  * Vendor PE matched `总市值 / TTM净利润` derived from Sina EXACTLY on 3/3.
  * Field 73 is TOTAL share capital: it satisfies the market-cap identity on 3/3, while fields
    72/76 (tradable capital) fail it for 000333 — a dual-listed name is what discriminates them,
    which is why the check was run on more than one symbol.

**PB is taken from the vendor, never derived.** A derived `price / 每股净资产` matched the vendor
for 600519 and 000001 but was WRONG for 000333 (2.800 vs 3.19), because a dual-listed company's
equity basis differs from the naive one. That single disagreement is the reason this provider
reports the vendor's own PB and does not compute one.

What is deliberately NOT reported
=================================
`营收`, `净利润`, `毛利率`, `净利率`, `EPS` and `ROE` are **not** available from this endpoint, and
no free source was found that reports them in a form that could be verified the way the fields
above were. They are therefore returned as `None` and surface in the Terminal as 暂无数据 with a
reason — never estimated, and never back-filled from the demo dataset. Filling the panel with
unverifiable numbers would defeat the point of having one.

Public but undocumented and unlicensed: no SLA, no compatibility guarantee. The positional field
layout is re-checked by an arity guard and by the market-cap identity on every fetch, so a silent
vendor reordering surfaces as a refusal rather than as wrong valuation numbers.
"""

import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.data.contracts.fundamental_data import (
    FundamentalDataContract,
    MetricProvenance,
)
from src.data.providers.base import ProviderError
from src.data.providers.fundamental_provider import (
    REPORT_PERIOD_NOT_DISCLOSED,
    FundamentalProvider,
)

TENCENT_FUNDAMENTAL_PROVIDER_ID = "tencent_valuation"
TENCENT_FUNDAMENTAL_PROVIDER_VERSION = "1.0.0-tencent-http"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="

# Positions verified across three symbols; see the module docstring.
_F_NAME, _F_CODE, _F_PRICE = 1, 2, 3
_F_TIMESTAMP = 30
_F_PE_TTM = 39
_F_FLOAT_MARKET_CAP = 44      # 流通市值, 亿元
_F_TOTAL_MARKET_CAP = 45      # 总市值, 亿元
_F_PB = 46
_F_TOTAL_SHARES = 73          # 总股本, 股 — discriminated from 流通股本 by the dual-listed case
_MIN_FIELDS = 74

_YI = 1e8                     # 亿
_EXCHANGE_PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
_CACHE_TTL_SECONDS = 30.0
# Valuation metrics move with price, so the identity is checked with a tolerance rather than
# exactly: the vendor's 总市值 and its price can be sampled a moment apart.
_MARKET_CAP_IDENTITY_TOLERANCE = 0.02


class TencentFundamentalProvider(FundamentalProvider):
    def __init__(self, timeout_seconds: float = 6.0, base_url: str = TENCENT_QUOTE_URL):
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url
        self._cache: Dict[str, Tuple[float, FundamentalDataContract]] = {}

    @property
    def provider_id(self) -> str:
        return TENCENT_FUNDAMENTAL_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return TENCENT_FUNDAMENTAL_PROVIDER_VERSION

    @property
    def source_label(self) -> str:
        return f"腾讯财经估值数据 ({TENCENT_FUNDAMENTAL_PROVIDER_ID})"

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

    def _fetch(self, vendor_code: str) -> str:
        request = urllib.request.Request(
            f"{self._base_url}{vendor_code}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; ashare-quant-terminal/1.0)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read().decode("gbk", errors="replace")
        except urllib.error.HTTPError as e:
            raise ProviderError(
                self.provider_id, f"valuation endpoint returned HTTP {e.code}."
            ) from None
        except Exception as e:
            raise ProviderError(
                self.provider_id,
                f"could not reach the valuation endpoint ({type(e).__name__}: {e}).",
            ) from None

    def _fields(self, raw: str, symbol: str) -> List[str]:
        if '="' not in raw:
            raise ProviderError(
                self.provider_id, f"unrecognised valuation response shape for '{symbol}'."
            )
        payload = raw.split('="', 1)[1].rstrip().rstrip(";").rstrip('"')
        if not payload.strip():
            raise ProviderError(
                self.provider_id,
                f"the valuation source has no data for '{symbol}' — it may not be a listed "
                "A-share code.",
            )
        fields = payload.split("~")
        if len(fields) < _MIN_FIELDS:
            raise ProviderError(
                self.provider_id,
                f"valuation response for '{symbol}' had {len(fields)} fields, fewer than the "
                f"{_MIN_FIELDS} this parser verified.",
            )
        return fields

    def _optional_number(self, raw: str) -> Optional[float]:
        """The vendor blanks a metric it cannot compute (e.g. PE for a loss-making company).
        A blank becomes None, which surfaces as 暂无数据 — never 0.0, which would read as a
        real measurement."""
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value != 0 else None

    def _required_number(self, fields: List[str], index: int, label: str,
                         symbol: str) -> float:
        try:
            return float(fields[index])
        except (TypeError, ValueError):
            raise ProviderError(
                self.provider_id,
                f"valuation for '{symbol}' has a non-numeric {label}: {fields[index]!r}.",
            ) from None

    def _trade_date(self, fields: List[str], symbol: str) -> str:
        stamp = fields[_F_TIMESTAMP]
        try:
            return datetime.strptime(stamp[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            raise ProviderError(
                self.provider_id,
                f"valuation for '{symbol}' has an unparseable timestamp {stamp!r}.",
            ) from None

    def get_fundamentals(self, symbol: str) -> FundamentalDataContract:
        cached = self._cache.get(symbol)
        if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        fields = self._fields(self._fetch(self._vendor_code(symbol)), symbol)

        price = self._required_number(fields, _F_PRICE, "price", symbol)
        total_shares = self._required_number(fields, _F_TOTAL_SHARES, "total shares", symbol)
        total_market_cap_yi = self._required_number(
            fields, _F_TOTAL_MARKET_CAP, "total market cap", symbol
        )
        if price <= 0 or total_shares <= 0 or total_market_cap_yi <= 0:
            raise ProviderError(
                self.provider_id,
                f"valuation for '{symbol}' reports a non-positive price, share count or market "
                "cap.",
            )

        # The layout is positional and undocumented. This identity is what pinned field 73 as
        # TOTAL rather than tradable share capital, so re-checking it on every fetch is how a
        # silent vendor reordering becomes a refusal instead of a wrong market cap.
        implied_yi = price * total_shares / _YI
        if abs(implied_yi - total_market_cap_yi) / total_market_cap_yi > \
                _MARKET_CAP_IDENTITY_TOLERANCE:
            raise ProviderError(
                self.provider_id,
                f"valuation for '{symbol}' fails its own market-cap identity "
                f"(price x shares = {implied_yi:.2f}亿 vs reported {total_market_cap_yi:.2f}亿) — "
                "the vendor's field order may have changed.",
            )

        pe_ttm = self._optional_number(fields[_F_PE_TTM])
        pb = self._optional_number(fields[_F_PB])
        contract = FundamentalDataContract(
            symbol=symbol.upper(),
            trade_date=self._trade_date(fields, symbol),
            # This endpoint reports valuation as of today's price; it does not disclose which
            # accounting period the earnings behind PE came from. Inventing a report date would
            # be fabrication, so the absence is stated.
            report_date=REPORT_PERIOD_NOT_DISCLOSED,
            announcement_date=REPORT_PERIOD_NOT_DISCLOSED,
            currency="CNY",
            # Not reported by this endpoint, and not verifiable from any free source found --
            # None here becomes 暂无数据 in the Terminal, never an estimate.
            revenue=None, net_income=None, eps_annual=None, eps_ttm=None,
            book_value_per_share=None, operating_cash_flow=None,
            shares_outstanding=total_shares,
            market_cap=total_market_cap_yi * _YI,
            pe_lyr=None,
            pe_ttm=pe_ttm,
            pe_ttm_status="VALID" if pe_ttm is not None else "UNAVAILABLE",
            pb=pb,
            pb_status="VALID" if pb is not None else "UNAVAILABLE",
            dividend_yield_ttm=None, dividend_yield_status="UNAVAILABLE",
            roe=None,
            provenance=MetricProvenance.PROVIDER_REPORTED,
            quality_status="VALID",
            provider=self.provider_id,
            provider_timestamp=datetime.now(),
            data_origin="REAL_PROVIDER",
        )
        self._cache[symbol] = (time.monotonic(), contract)
        return contract
