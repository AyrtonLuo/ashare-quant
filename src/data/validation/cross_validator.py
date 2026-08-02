"""
cross_validator.py — Cross-Provider Validation Engine comparing Primary vs Secondary feeds.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional
from src.data.contracts.market_data import MarketDataContract


class CrossValidationStatus(str, Enum):
    MATCH = "MATCH"
    MINOR_MISMATCH = "MINOR_MISMATCH"
    MAJOR_MISMATCH = "MAJOR_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CrossValidationResult:
    symbol: str
    field_name: str
    primary_val: float
    secondary_val: float
    abs_diff: float
    rel_diff_pct: float
    status: CrossValidationStatus


class CrossProviderValidator:
    """Compares Primary and Secondary provider contracts for consistency."""

    @staticmethod
    def compare_market_close(
        primary: MarketDataContract, secondary: Optional[MarketDataContract]
    ) -> CrossValidationResult:
        if not secondary:
            return CrossValidationResult(
                symbol=primary.symbol,
                field_name="close_price",
                primary_val=primary.close_price,
                secondary_val=0.0,
                abs_diff=0.0,
                rel_diff_pct=0.0,
                status=CrossValidationStatus.UNKNOWN
            )

        p_close = primary.close_price
        s_close = secondary.close_price
        abs_diff = abs(p_close - s_close)
        rel_diff_pct = (abs_diff / p_close) * 100.0 if p_close > 0 else 0.0

        if rel_diff_pct < 0.1:
            status = CrossValidationStatus.MATCH
        elif rel_diff_pct < 1.0:
            status = CrossValidationStatus.MINOR_MISMATCH
        else:
            status = CrossValidationStatus.MAJOR_MISMATCH

        return CrossValidationResult(
            symbol=primary.symbol,
            field_name="close_price",
            primary_val=p_close,
            secondary_val=s_close,
            abs_diff=round(abs_diff, 4),
            rel_diff_pct=round(rel_diff_pct, 4),
            status=status
        )
