"""
market_session.py — Market Session Engine tracking A-Share trading sessions & freshness.
"""

from enum import Enum
from datetime import datetime, time


class MarketSessionState(str, Enum):
    PRE_MARKET = "PRE_MARKET"        # 09:00 - 09:30
    OPEN = "OPEN"                    # 09:30 - 11:30, 13:00 - 15:00
    BREAK = "BREAK"                  # 11:30 - 13:00
    CLOSE = "CLOSE"                  # 15:00 - 09:00 next day
    HOLIDAY = "HOLIDAY"


class MarketSessionEngine:
    """Tracks China A-Share intraday market session state and validates UI tags."""

    @staticmethod
    def get_market_session(dt: datetime, is_trading_day: bool = True) -> MarketSessionState:
        if not is_trading_day:
            return MarketSessionState.HOLIDAY

        t = dt.time()
        pre_start = time(9, 0)
        open_morning_start = time(9, 30)
        open_morning_end = time(11, 30)
        open_afternoon_start = time(13, 0)
        open_afternoon_end = time(15, 0)

        if pre_start <= t < open_morning_start:
            return MarketSessionState.PRE_MARKET
        elif open_morning_start <= t <= open_morning_end or open_afternoon_start <= t <= open_afternoon_end:
            return MarketSessionState.OPEN
        elif open_morning_end < t < open_afternoon_start:
            return MarketSessionState.BREAK
        else:
            return MarketSessionState.CLOSE
