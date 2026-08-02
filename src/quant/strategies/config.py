"""
config.py — Strategy Configuration System Schema & Rebalance Calendar Engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from src.data.calendar.trading_calendar import TradingCalendar


class RebalanceFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class UniverseType(str, Enum):
    ALL_A_SHARE = "ALL_A_SHARE"
    CUSTOM_SYMBOLS = "CUSTOM_SYMBOLS"
    INDEX_CONSTITUENTS = "INDEX_CONSTITUENTS"


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    strategy_version: str
    universe_type: UniverseType
    symbols: List[str]
    factor_weights: Dict[str, float]
    rebalance_frequency: RebalanceFrequency
    max_position_limit: float = 0.20        # Max 20% weight per stock
    max_turnover_limit: float = 0.50        # Max 50% rebalance turnover
    min_history_days: int = 20
    commission_rate: float = 0.00025
    stamp_duty_rate: float = 0.0005
    slippage_rate: float = 0.0001
    benchmark_id: str = "equal_weight_benchmark"
    start_date: str = "2020-01-01"
    end_date: str = "2026-08-01"


class RebalanceCalendarEngine:
    """Uses Canonical TradingCalendar to determine official rebalancing dates."""

    @staticmethod
    def filter_rebalance_dates(
        trading_days: List[str], frequency: RebalanceFrequency
    ) -> List[str]:
        if frequency == RebalanceFrequency.DAILY:
            return trading_days
        elif frequency == RebalanceFrequency.WEEKLY:
            # Select every 5th trading day
            return trading_days[::5]
        elif frequency == RebalanceFrequency.MONTHLY:
            # Select every 20th trading day
            return trading_days[::20]
        else:
            return trading_days
