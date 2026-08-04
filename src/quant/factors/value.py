"""
value.py — Valuation Factor Adapter (PE / PB / Dividend Yield) with MetricProvenance tracking & PIT enforcement.
"""

from datetime import datetime
from typing import Optional
from src.quant.factors.base import BaseFactor, FactorValue, FactorStatus
from src.data.contracts.fundamental_data import MetricProvenance


class ValuationFactorAdapter(BaseFactor):
    def __init__(self, metric_type: str = "pe_ttm"):
        self.metric_type = metric_type

    @property
    def name(self) -> str:
        return f"valuation_{self.metric_type}"

    @property
    def version(self) -> str:
        return "1.0.0"

    def compute_from_fundamental(
        self, symbol: str, val: Optional[float], provenance: MetricProvenance, effective_date: str, as_of: datetime
    ) -> FactorValue:
        # Enforce temporal provenance check: CURRENT_ONLY / NOT_PIT_VERIFIED / UNAVAILABLE cannot produce a valid factor score
        if provenance in [MetricProvenance.CURRENT_ONLY, MetricProvenance.NOT_PIT_VERIFIED, MetricProvenance.UNAVAILABLE]:
            return FactorValue(
                symbol=symbol, factor_name=self.name, factor_version=self.version,
                raw_value=None, effective_date=effective_date, as_of=as_of,
                status=FactorStatus.NOT_APPLICABLE,
                quality_notes=f"Unverified PIT Provenance: {provenance.value}"
            )

        if val is None or val <= 0:
            return FactorValue(
                symbol=symbol, factor_name=self.name, factor_version=self.version,
                raw_value=None, effective_date=effective_date, as_of=as_of,
                status=FactorStatus.NOT_APPLICABLE,
                quality_notes=f"Provenance: {provenance.value}"
            )

        return FactorValue(
            symbol=symbol, factor_name=self.name, factor_version=self.version,
            raw_value=float(val), effective_date=effective_date, as_of=as_of,
            status=FactorStatus.VALID,
            quality_notes=f"Provenance: {provenance.value}"
        )

    def compute(self, symbol: str, prices: list, effective_date: str, as_of: datetime) -> FactorValue:
        raise NotImplementedError("Use compute_from_fundamental method for valuation metrics")
