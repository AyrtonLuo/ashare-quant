"""
revision_model.py — DataRevision Contract for Historical & Fundamental Data Revision Control.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any
from src.data.contracts.fundamental_data import MetricProvenance


@dataclass(frozen=True)
class DataRevision:
    """
    Represents a single immutable version of a data point (symbol, field, effective_date).
    Supports restatements, financial corrections, and provider updates over time.
    """
    record_id: str
    symbol: str
    field: str                          # e.g., "close", "pe", "pe_ttm", "revenue", "net_income"
    effective_date: str                 # "YYYY-MM-DD"
    value: Any                          # The observed numeric or categorical value
    provider: str                       # e.g., "tushare_pro", "akshare"
    available_at: datetime              # Timestamp when this revision became legally visible
    received_at: datetime               # Timestamp when payload arrived in system
    revision_id: str                    # Sequence/version identifier e.g., "rev_001"
    dataset_version: str                # Dataset version identifier e.g., "ds_v1.0"
    is_current: bool = True             # Latest version at present real-time (not PIT)
    supersedes_revision_id: Optional[str] = None
    provenance: MetricProvenance = MetricProvenance.PROVIDER_REPORTED
    quality_status: str = "VALID"
    provider_field: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    as_of_limit: Optional[datetime] = None
