"""
gate.py — DataTrustGate: Gatekeeper enforcing data validity before Quant Engine consumption.
"""

from typing import Tuple, List, Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract


class DataTrustGate:
    """Gatekeeper enforcing that only VALID data enters Quant Engine."""

    @staticmethod
    def validate_market_data(contract: MarketDataContract) -> Tuple[bool, List[str]]:
        errors = []
        if contract.high_price < contract.low_price:
            errors.append(f"High price ({contract.high_price}) < Low price ({contract.low_price})")
        if contract.close_price <= 0:
            errors.append(f"Invalid non-positive close price: {contract.close_price}")
        if contract.volume < 0:
            errors.append(f"Negative volume: {contract.volume}")
        if contract.quality_status != "VALID":
            errors.append(f"Quality status is not VALID: {contract.quality_status}")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def validate_fundamental_data(contract: FundamentalDataContract) -> Tuple[bool, List[str]]:
        errors = []
        if contract.shares_outstanding <= 0:
            errors.append(f"Invalid shares_outstanding: {contract.shares_outstanding}")
        if contract.market_cap <= 0:
            errors.append(f"Invalid market_cap: {contract.market_cap}")
        if contract.quality_status != "VALID":
            errors.append(f"Fundamental quality_status is not VALID: {contract.quality_status}")

        is_valid = len(errors) == 0
        return is_valid, errors
