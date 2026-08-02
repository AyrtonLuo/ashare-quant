"""
lineage.py — Data Lineage & Provenance Metadata Contract.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class DataLineageContract:
    symbol: str
    field_name: str
    observed_value: Any
    provider_primary: str
    provider_secondary: Optional[str]
    endpoint_name: str
    retrieved_at: datetime
    trade_date: str
    report_date: Optional[str]
    announcement_date: Optional[str]
    calculation_version: str
    transformation_applied: str
    verification_status: str     # "VERIFIED", "SUSPECT_MISMATCH", "UNVERIFIED"
    quality_score: float         # 0.0 to 1.0
