"""
ma_cross_strategy.py
基于接口规范的双均线择时与组合构建策略 (MACrossStrategy)
"""

import pandas as pd
from typing import Optional, Dict, Any, List
from src.strategy.interface import Strategy
from src.strategy.signal import StrategySignal
from src.strategy.ma_cross import generate_ma_cross_signals
from src.data.provider import MarketDataProvider


class MACrossStrategy(Strategy):
    def __init__(self, symbols: List[str], short_window: int = 5, long_window: int = 10):
        super().__init__(strategy_id="MA_Cross_v1")
        self.symbols = symbols
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(
        self,
        data_provider: MarketDataProvider,
        portfolio_state: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> StrategySignal:
        ts = timestamp or pd.Timestamp.now().strftime("%Y-%m-%d")
        target_weights = {}
        scores = {}

        for sym in self.symbols:
            hist_df = data_provider.get_history(sym, end_date=ts)
            if hist_df is not None and len(hist_df) >= self.long_window:
                ma_df = generate_ma_cross_signals(hist_df, self.short_window, self.long_window)
                latest_sig = ma_df['signal'].iloc[-1]
                scores[sym] = float(latest_sig)
            else:
                scores[sym] = 0.0

        # 按多头信号均分多头仓位
        bull_symbols = [s for s, sig in scores.items() if sig > 0.5]
        if bull_symbols:
            eq_weight = 1.0 / len(bull_symbols)
            for s in bull_symbols:
                target_weights[s] = round(eq_weight, 4)

        return StrategySignal(
            timestamp=ts,
            strategy_id=self.strategy_id,
            symbols=self.symbols,
            target_weights=target_weights,
            scores=scores
        )
