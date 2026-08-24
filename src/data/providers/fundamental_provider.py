"""
fundamental_provider.py — FundamentalProvider ABC and the demo implementation (Terminal T4).

A THIRD, separate data capability. Quotes (`quote_provider.py`), daily history
(`history_provider.py`) and fundamentals each declare their own provider and their own source
label — they are never collapsed into a single "data source" claim, because they come from
different endpoints with different update frequencies and different reliability.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.providers.base import ProviderError

GOLDEN_FUNDAMENTAL_PROVIDER_ID = "golden_demo_fundamental"

# Reported on the contract when the source simply does not disclose the accounting period behind
# a valuation metric. Better than inventing a plausible-looking report date.
REPORT_PERIOD_NOT_DISCLOSED = "NOT_DISCLOSED_BY_SOURCE"


class FundamentalProvider(ABC):
    """The latest available fundamental / valuation snapshot for one symbol."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def provider_version(self) -> str: ...

    @property
    @abstractmethod
    def source_label(self) -> str:
        """Human-readable name of THIS data source, shown on the fundamental panel only, so a
        user is never told that fundamentals came from the quote or history feed."""
        ...

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> FundamentalDataContract:
        """Must raise ProviderError on any failure — never return a partially-populated contract
        with invented values, and never fall back to another source."""
        ...


class GoldenFundamentalProvider(FundamentalProvider):
    """DEMO provider over the certified GOLDEN_DATASET fundamentals."""

    def __init__(self, records_by_symbol: Dict[str, List[FundamentalDataContract]]):
        self._records = records_by_symbol

    @property
    def provider_id(self) -> str:
        return GOLDEN_FUNDAMENTAL_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return "1.0.0-golden-demo"

    @property
    def source_label(self) -> str:
        return "演示数据集 (DEMO DATA)"

    def get_fundamentals(self, symbol: str) -> FundamentalDataContract:
        records = self._records.get(symbol)
        if not records:
            raise ProviderError(
                self.provider_id, f"no GOLDEN_DATASET fundamentals available for '{symbol}'."
            )
        return records[-1]
