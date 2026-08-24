"""
gate.py — DataTrustGate: Gatekeeper enforcing data validity before Quant Engine consumption.
"""

from datetime import datetime, timezone
from typing import Tuple, List, Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.news_announcement import NewsAnnouncementContract
from src.data.contracts.derived import DerivedDataContract
from src.data.contracts.quote import QuoteContract


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

    @staticmethod
    def validate_news_announcement(contract: NewsAnnouncementContract) -> Tuple[bool, List[str]]:
        """AI_QUANT_RESEARCH_ANALYST — a checkpoint deliberately independent of, and in addition
        to, NewsAnnouncementContract.__post_init__'s structural checks and PITGate's temporal
        filtering: this is the Validation stage of the directive's own pipeline, the last
        business-rule checkpoint before an item may enter the Evidence Layer."""
        errors = []
        if contract.quality_status != "VALID":
            errors.append(f"News quality_status is not VALID: {contract.quality_status}")
        if not (0.0 <= contract.relevance_score <= 1.0):
            errors.append(f"relevance_score out of [0,1] range: {contract.relevance_score}")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if contract.published_at > now:
            errors.append(f"published_at ({contract.published_at.isoformat()}) is in the future.")
        if contract.received_at is None:
            errors.append("received_at is missing — cannot establish PIT visibility, refusing to treat as always-available.")
        if contract.available_at is None:
            errors.append("available_at is missing — cannot establish PIT visibility, refusing to treat as always-available.")
        if contract.received_at is not None and contract.received_at < contract.published_at:
            errors.append(
                f"received_at ({contract.received_at.isoformat()}) is before published_at "
                f"({contract.published_at.isoformat()}) — cannot have received something before it existed."
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def validate_technical_indicator(contract: DerivedDataContract) -> Tuple[bool, List[str]]:
        """AI_QUANT_RESEARCH_ANALYST — validates a technical-indicator DerivedDataContract before
        it may enter the Evidence Layer. Does not re-derive the indicator's math (that is
        technical/indicators.py's job) — only checks internal consistency and completeness."""
        errors = []
        if contract.quality_status not in ("VALID", "INSUFFICIENT_WARM_UP"):
            errors.append(f"Technical indicator quality_status is not recognized: {contract.quality_status}")
        if contract.warm_up_satisfied and contract.calculated_value is None:
            errors.append("warm_up_satisfied=True but calculated_value is None — inconsistent state.")
        if not contract.warm_up_satisfied and contract.quality_status == "VALID":
            errors.append("warm_up_satisfied=False must not be reported as quality_status='VALID'.")
        if contract.effective_date is None:
            errors.append("effective_date is missing — a technical indicator value must state which date it describes.")
        if contract.input_price_basis not in (
            "PIT_ADJUSTED", "RAW", "NOT_APPLICABLE", "VENDOR_FORWARD_ADJUSTED",
        ):
            errors.append(f"Unknown input_price_basis: {contract.input_price_basis}")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def validate_quote(contract: QuoteContract, max_age_seconds: Optional[float] = None,
                       now: Optional[datetime] = None) -> Tuple[bool, List[str]]:
        """TERMINAL step T1 — validates a QuoteContract before the Terminal may display it.

        Checks internal coherence, not vendor honesty: a quote whose high is below its last
        price, or whose open sits outside its own high/low band, is internally contradictory and
        must not be shown to a user as fact regardless of who sent it.

        `max_age_seconds` is OPTIONAL and off by default. Staleness is a presentation decision
        (a Sunday-evening quote is stale but perfectly valid data), so this gate reports it only
        when a caller states a threshold, and never silently drops an old quote.
        """
        errors = []

        if contract.high_price < contract.low_price:
            errors.append(
                f"high_price {contract.high_price} is below low_price {contract.low_price}."
            )
        for field_name in ("last_price", "open_price"):
            value = getattr(contract, field_name)
            if value > contract.high_price or value < contract.low_price:
                errors.append(
                    f"{field_name} {value} lies outside the session range "
                    f"[{contract.low_price}, {contract.high_price}]."
                )
        # Turnover without volume (or the reverse) is incoherent; either both moved or neither
        # did. Reported rather than silently normalised to zero.
        if contract.volume == 0 and contract.amount > 0:
            errors.append("amount is positive but volume is zero — inconsistent turnover.")
        if contract.amount == 0 and contract.volume > 0:
            errors.append("volume is positive but amount is zero — inconsistent turnover.")
        if contract.trading_status == "SUSPENDED" and contract.volume > 0:
            errors.append("trading_status is SUSPENDED but volume is positive.")

        if max_age_seconds is not None:
            age = contract.age_seconds(now)
            if age > max_age_seconds:
                errors.append(
                    f"quote is {age:.0f}s old, exceeding the caller's max_age_seconds "
                    f"{max_age_seconds:.0f}."
                )

        is_valid = len(errors) == 0
        return is_valid, errors
