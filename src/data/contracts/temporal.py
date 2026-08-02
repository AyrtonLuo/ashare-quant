"""
temporal.py — Unified Temporal Data Contract & Classification Enums.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class TemporalClassification(str, Enum):
    HISTORICAL = "HISTORICAL"
    POINT_IN_TIME = "POINT_IN_TIME"
    REALTIME = "REALTIME"
    DELAYED_REALTIME = "DELAYED_REALTIME"
    DERIVED = "DERIVED"


class UIInterestTag(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    LAST_CLOSE = "LAST_CLOSE"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class TemporalDataContract:
    symbol: str                     # e.g., "600519.SH"
    value: Any                      # Observed value (price, PE, volume, etc.)
    temporal_class: TemporalClassification
    
    event_time: datetime            # When the value occurred in reality
    effective_date: str             # Date the value describes ("YYYY-MM-DD")
    available_at: datetime          # When the system could legally know this value (PIT Protection)
    received_at: datetime           # When provider payload arrived in system
    as_of: datetime                 # Query cutoff timestamp
    
    provider_timestamp: Optional[datetime] = None
    provider_id: str = "tushare_pro_primary"
    quality_status: str = "VALID"

    @property
    def latency_seconds(self) -> float:
        return (self.received_at - self.event_time).total_seconds()

    @property
    def ui_tag(self) -> UIInterestTag:
        if self.temporal_class == TemporalClassification.REALTIME:
            return UIInterestTag.LIVE
        elif self.temporal_class == TemporalClassification.DELAYED_REALTIME:
            return UIInterestTag.DELAYED
        elif self.temporal_class == TemporalClassification.HISTORICAL:
            return UIInterestTag.HISTORICAL
        else:
            return UIInterestTag.LAST_CLOSE
