"""
cross_provider.py — Controlled Cross-Provider Reconciliation Layer (TuShare Pro vs AkShare).
Performs field-by-field comparative validation across providers with explicit tolerance classification.
Prevents silent overwrites while retaining provenance for both primary and secondary sources.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from src.data.contracts.market_data import MarketDataContract


class ReconciliationStatus(str, Enum):
    MATCH = "MATCH"
    ACCEPTABLE_DIFFERENCE = "ACCEPTABLE_DIFFERENCE"
    MATERIAL_DIFFERENCE = "MATERIAL_DIFFERENCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


@dataclass(frozen=True)
class ReconciliationReport:
    symbol: str
    trade_date: str
    primary_provider: str
    secondary_provider: str
    status: ReconciliationStatus
    close_relative_error: float
    volume_relative_error: float
    difference_details: Dict[str, Any]


class CrossProviderReconciler:
    """
    Controlled reconciliation engine comparing primary and secondary data providers.
    Enforces numerical tolerances and rejects silent data overwrites.
    """

    DEFAULT_MATCH_TOLERANCE = 0.001         # 0.1% difference -> MATCH
    DEFAULT_ACCEPTABLE_TOLERANCE = 0.01     # 1.0% difference -> ACCEPTABLE_DIFFERENCE

    @classmethod
    def reconcile_market_data(
        cls,
        primary_contract: Optional[MarketDataContract],
        secondary_contract: Optional[MarketDataContract],
        match_tol: float = DEFAULT_MATCH_TOLERANCE,
        acceptable_tol: float = DEFAULT_ACCEPTABLE_TOLERANCE
    ) -> ReconciliationReport:
        if primary_contract is None or secondary_contract is None:
            p_prov = getattr(primary_contract, 'provider_id', getattr(primary_contract, 'provider', 'UNAVAILABLE')) if primary_contract else "UNAVAILABLE"
            s_prov = getattr(secondary_contract, 'provider_id', getattr(secondary_contract, 'provider', 'UNAVAILABLE')) if secondary_contract else "UNAVAILABLE"
            return ReconciliationReport(
                symbol=primary_contract.symbol if primary_contract else (secondary_contract.symbol if secondary_contract else "UNKNOWN"),
                trade_date=primary_contract.trading_date if primary_contract else (secondary_contract.trading_date if secondary_contract else "UNKNOWN"),
                primary_provider=p_prov,
                secondary_provider=s_prov,
                status=ReconciliationStatus.PROVIDER_UNAVAILABLE,
                close_relative_error=0.0,
                volume_relative_error=0.0,
                difference_details={"message": "PROVIDER_UNAVAILABLE: One or both providers failed to return contract."}
            )

        p_prov = getattr(primary_contract, 'provider_id', getattr(primary_contract, 'provider', 'tushare_pro_primary'))
        s_prov = getattr(secondary_contract, 'provider_id', getattr(secondary_contract, 'provider', 'akshare_secondary'))

        p_close = primary_contract.close_price
        s_close = secondary_contract.close_price
        close_err = abs(p_close - s_close) / max(abs(p_close), 1e-6)

        p_vol = primary_contract.volume
        s_vol = secondary_contract.volume
        vol_err = abs(p_vol - s_vol) / max(abs(p_vol), 1e-6)

        max_err = max(close_err, vol_err)
        if max_err <= match_tol:
            status = ReconciliationStatus.MATCH
        elif max_err <= acceptable_tol:
            status = ReconciliationStatus.ACCEPTABLE_DIFFERENCE
        else:
            status = ReconciliationStatus.MATERIAL_DIFFERENCE

        diff_details = {
            "primary_close": p_close,
            "secondary_close": s_close,
            "primary_volume": p_vol,
            "secondary_volume": s_vol,
            "close_diff": round(p_close - s_close, 4),
            "volume_diff": round(p_vol - s_vol, 4)
        }

        return ReconciliationReport(
            symbol=primary_contract.symbol,
            trade_date=primary_contract.trading_date,
            primary_provider=p_prov,
            secondary_provider=s_prov,
            status=status,
            close_relative_error=round(close_err, 6),
            volume_relative_error=round(vol_err, 6),
            difference_details=diff_details
        )
