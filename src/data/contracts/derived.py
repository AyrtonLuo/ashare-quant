"""
derived.py — Derived Data Lineage Contract for calculated metrics (e.g. Realtime PE, Momentum).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any, Optional, Dict
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification


@dataclass(frozen=True)
class DerivedDataContract:
    symbol: str
    metric_name: str
    calculated_value: Any
    derived_at: datetime
    formula_version: str
    input_data_ids: List[str]       # Micro-IDs of input temporal contracts
    input_as_of: datetime
    quality_status: str = "VALID"
    input_snapshot_id: Optional[str] = None
    calculation_timestamp: Optional[datetime] = None

    # AI_QUANT_RESEARCH_ANALYST — Technical Indicator canonical calculation contract fields.
    # Trailing-defaulted so both existing construction call sites (test_derived_data_lineage.py,
    # test_mixed_temporal_input.py) remain valid unmodified. Reuses this class rather than
    # introducing a parallel TechnicalIndicatorContract — this class's own docstring already
    # names "Momentum" as an intended use case, and MA/RSI/MACD are the same kind of thing: a
    # calculated value derived from underlying data with explicit lineage (input_data_ids).
    effective_date: Optional[str] = None       # "YYYY-MM-DD" this value DESCRIBES — distinct
                                                # from derived_at/calculation_timestamp (when it
                                                # was computed); required for any real indicator,
                                                # optional here only for backward compatibility.
    parameters: Dict[str, Any] = field(default_factory=dict)  # e.g. {"window": 20}
    input_price_basis: str = "PIT_ADJUSTED"    # "PIT_ADJUSTED" | "RAW" — MUST be explicit, never
                                                # ambiguous, per the directive's explicit item 5.
    lookback_window: Optional[int] = None      # trading days of input history this value required
    warm_up_satisfied: bool = True             # False if insufficient history existed — see
                                                # quality_status="INSUFFICIENT_WARM_UP" convention
    # Provenance of the UNDERLYING price series feeding this calculation (not of the calculation
    # itself, which is always LOCAL_CANONICAL_CALCULATION — see technical/indicators.py). Same
    # 4-tag vocabulary used project-wide.
    data_origin: str = "SYNTHETIC_DATA"

    def __post_init__(self):
        if self.calculation_timestamp is None:
            object.__setattr__(self, 'calculation_timestamp', self.derived_at)
        if self.lookback_window is not None and self.lookback_window <= 0:
            raise ValueError(f"FAIL CLOSED: invalid lookback_window {self.lookback_window} for {self.symbol}.")
        if self.input_price_basis not in ("PIT_ADJUSTED", "RAW"):
            raise ValueError(f"FAIL CLOSED: unknown input_price_basis '{self.input_price_basis}' for {self.symbol}.")

    def to_temporal_contract(self) -> TemporalDataContract:
        return TemporalDataContract(
            symbol=self.symbol,
            value=self.calculated_value,
            temporal_class=TemporalClassification.DERIVED,
            event_time=self.derived_at,
            effective_date=self.derived_at.strftime("%Y-%m-%d"),
            available_at=self.derived_at,
            received_at=self.derived_at,
            as_of=self.input_as_of,
            quality_status=self.quality_status
        )
