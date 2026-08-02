"""
base.py — Abstract Factor Base Class & Factor Value Schema.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class FactorStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FactorValue:
    symbol: str
    factor_name: str
    factor_version: str
    raw_value: Optional[float]
    effective_date: str
    as_of: datetime
    status: FactorStatus
    quality_notes: str = ""


class BaseFactor(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def version(self) -> str: pass

    @abstractmethod
    def compute(self, symbol: str, prices: List[float], effective_date: str, as_of: datetime) -> FactorValue:
        pass
