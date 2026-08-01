"""
signal.py
统一策略信号模型 (StrategySignal)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
import pandas as pd


@dataclass
class StrategySignal:
    timestamp: str
    strategy_id: str
    symbols: List[str]
    target_weights: Dict[str, float]  # e.g., {"600519": 0.20, "000001": 0.15}
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "symbols": self.symbols,
            "target_weights": self.target_weights,
            "scores": self.scores,
            "metadata": self.metadata
        }

    def to_dataframe(self) -> pd.DataFrame:
        records = []
        for sym in self.symbols:
            records.append({
                "symbol": sym,
                "target_weight": self.target_weights.get(sym, 0.0),
                "score": self.scores.get(sym, 0.0)
            })
        return pd.DataFrame(records)
