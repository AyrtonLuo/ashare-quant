"""
schemas.py
AI 智能研报数据结构定义 (schemas)
定义 ResearchContext, DiagnosticResult, ResearchReport 等结构化对象。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DiagnosticResult:
    level: str  # "LOW", "MODERATE", "HIGH", "CRITICAL"
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchContext:
    experiment_id: str
    strategy_id: str
    universe: List[str]
    date_range: str
    benchmark: str
    performance_metrics: Dict[str, Any]
    ml_metrics: Dict[str, Any] = field(default_factory=dict)
    factor_importances: Dict[str, float] = field(default_factory=dict)
    decay_info: Dict[str, Any] = field(default_factory=dict)
    overfitting_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "universe": self.universe,
            "date_range": self.date_range,
            "benchmark": self.benchmark,
            "performance_metrics": self.performance_metrics,
            "ml_metrics": self.ml_metrics,
            "factor_importances": self.factor_importances,
            "decay_info": self.decay_info,
            "overfitting_info": self.overfitting_info
        }
