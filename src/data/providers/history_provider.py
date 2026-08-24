"""
history_provider.py — MarketHistoryProvider ABC and the demo implementation (Terminal T3.5).

A SERIES capability, deliberately separate from `UnifiedDataProvider.fetch_market_data(symbol,
trade_date)`. That method returns ONE bar for ONE date; building a 120-bar series through it
would mean 120 network round-trips, which is why the Terminal needed a new shape rather than a
new caller of the old one.

Mirrors the split already used for quotes (`quote_provider.py` / `sina_quote_provider.py`):
the ABC and the demo provider live here, and each real vendor gets its own module.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.data.contracts.market_data import MarketDataContract
from src.data.providers.base import ProviderError

GOLDEN_HISTORY_PROVIDER_ID = "golden_demo_history"

# The longest warm-up any Terminal indicator needs (MACD: slow 26 + signal 9 - 1). A series
# shorter than this cannot produce a single valid MACD value, so the Terminal reports 暂无数据
# rather than showing a partially-populated technical panel.
MIN_BARS_FOR_FULL_TECHNICALS = 34


class MarketHistoryProvider(ABC):
    """Daily bars for one symbol, most recent last."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def provider_version(self) -> str: ...

    @property
    @abstractmethod
    def input_price_basis(self) -> str:
        """How the returned prices are adjusted — one of the DerivedDataContract vocabulary.
        Exposed on the PROVIDER rather than inferred by the caller, because a caller that guesses
        wrong labels every downstream indicator with a false price basis."""
        ...

    @abstractmethod
    def get_daily_bars(self, symbol: str, limit: int = 120) -> List[MarketDataContract]:
        """Ascending by trading_date. Must raise ProviderError on any failure — never return a
        short series padded from another source, and never fabricate a missing bar."""
        ...


class GoldenHistoryProvider(MarketHistoryProvider):
    """DEMO provider over the certified GOLDEN_DATASET bars. Structurally incapable of returning
    anything stamped `REAL_PROVIDER`: it only ever hands back contracts it was given, which the
    golden seed stamps `GOLDEN_DATASET`."""

    def __init__(self, bars_by_symbol: Dict[str, List[MarketDataContract]]):
        self._bars = bars_by_symbol

    @property
    def provider_id(self) -> str:
        return GOLDEN_HISTORY_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return "1.0.0-golden-demo"

    @property
    def input_price_basis(self) -> str:
        return "RAW"   # the golden seed carries adj_factor 1.0 and unadjusted closes

    def get_daily_bars(self, symbol: str, limit: int = 120) -> List[MarketDataContract]:
        bars = self._bars.get(symbol)
        if not bars:
            raise ProviderError(
                self.provider_id, f"no GOLDEN_DATASET bars available for '{symbol}'."
            )
        return sorted(bars, key=lambda b: b.trading_date)[-limit:]
