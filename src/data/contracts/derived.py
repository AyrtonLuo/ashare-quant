"""
derived.py — Derived Data Lineage Contract for calculated metrics (e.g. Realtime PE).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Any
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
