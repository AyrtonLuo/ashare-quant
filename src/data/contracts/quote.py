"""
quote.py — QuoteContract: a point-in-time market quote for the consumer Terminal.

Terminal directive step T1. This is the one genuinely new data shape the Terminal needs, and it
exists because the rest of this codebase has no notion of "the price right now":
`UnifiedDataProvider.fetch_market_data(symbol, trade_date)` returns a COMPLETED DAILY BAR keyed
by date, and `MarketDataContract` carries no last-traded price, no intraday change, and no
as-of timestamp finer than a date.

`QuoteContract` is additive. It does not replace `MarketDataContract`, is not consumed by the
PIT/backtest/replay engines, and changes nothing about how certified research runs work — the
research core and the Terminal are two consumers of the same provider layer, not one rewritten
for the other.

Two properties are enforced by the type rather than left to UI convention, because the CEO
directive requires the Terminal to always answer "这个价格是几点的" and "数据来自哪里":

- **`quoted_at` and `received_at` are both required.** The vendor's own timestamp and the moment
  we received it are different facts, and conflating them is how a stale quote comes to look
  live. `freshness` is derived from them, never asserted independently.
- **`data_origin` uses the project-wide four-tag vocabulary.** A `GOLDEN_DATASET` quote can never
  present itself as `REAL_PROVIDER`, so the Terminal's DEMO DATA badge is driven by the data
  itself rather than by a UI flag someone could forget to set.

`change` and `change_pct` are COMPUTED here from `last_price` and `prev_close`, never taken from
a vendor field. Vendors disagree on whether change is versus previous close or previous
settlement, and on how they round; deriving it locally means the number shown always matches the
two prices shown beside it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# The same four-tag provenance vocabulary used project-wide — not a new one.
VALID_QUOTE_DATA_ORIGINS = (
    "REAL_PROVIDER", "LOCAL_PRODUCTION_VERIFICATION_DATA", "GOLDEN_DATASET", "SYNTHETIC_DATA",
)
VALID_QUOTE_TRADING_STATUS = ("NORMAL", "SUSPENDED", "HALTED", "PRE_OPEN", "CLOSED")


@dataclass(frozen=True)
class QuoteContract:
    symbol: str
    display_name: str
    last_price: float
    prev_close: float
    open_price: float
    high_price: float
    low_price: float
    volume: float                # shares traded so far in the session
    amount: float                # turnover in RMB so far in the session
    quoted_at: datetime          # the vendor's own timestamp for this quote
    received_at: datetime        # when THIS system received it — a different fact
    market_session: str          # MarketSessionState value
    trading_status: str
    provider_id: str
    data_origin: str = "SYNTHETIC_DATA"   # fail-closed default, as everywhere else
    currency: str = "CNY"

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("FAIL CLOSED: QuoteContract.symbol must not be empty.")
        if not self.provider_id:
            raise ValueError("FAIL CLOSED: QuoteContract.provider_id must not be empty.")
        if self.data_origin not in VALID_QUOTE_DATA_ORIGINS:
            raise ValueError(
                f"FAIL CLOSED: unknown QuoteContract.data_origin '{self.data_origin}' — must be "
                f"one of {VALID_QUOTE_DATA_ORIGINS}."
            )
        if self.trading_status not in VALID_QUOTE_TRADING_STATUS:
            raise ValueError(
                f"FAIL CLOSED: unknown QuoteContract.trading_status '{self.trading_status}'."
            )
        for field_name in ("last_price", "prev_close", "open_price", "high_price", "low_price"):
            value = getattr(self, field_name)
            if value is None or value <= 0:
                raise ValueError(
                    f"FAIL CLOSED: QuoteContract.{field_name} must be a positive price "
                    f"(got {value!r})."
                )
        for field_name in ("volume", "amount"):
            value = getattr(self, field_name)
            if value is None or value < 0:
                raise ValueError(
                    f"FAIL CLOSED: QuoteContract.{field_name} must not be negative "
                    f"(got {value!r})."
                )
        # A quote we received before the vendor claims to have produced it is incoherent, and
        # silently accepting it would let a bad clock masquerade as a fresh price.
        if self.received_at < self.quoted_at:
            raise ValueError(
                "FAIL CLOSED: received_at precedes quoted_at — the quote cannot have arrived "
                "before it existed."
            )

    @property
    def change(self) -> float:
        """Computed, never vendor-reported — see the module docstring."""
        return round(self.last_price - self.prev_close, 6)

    @property
    def change_pct(self) -> float:
        return round((self.last_price - self.prev_close) / self.prev_close * 100.0, 6)

    @property
    def is_demo(self) -> bool:
        """Drives the Terminal's DEMO DATA badge from the data itself, so the badge cannot be
        forgotten by a UI author."""
        return self.data_origin != "REAL_PROVIDER"

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        reference = now or datetime.now()
        return max(0.0, (reference - self.quoted_at).total_seconds())
