"""
schema.py
ResearchPlan 结构化模式与 PlanningError 规划异常类
确保所有 AI / ReAct Agent 规划输入都是 Deterministic, Schema-Validated 且符合 A 股数据防污染规范的。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


class PlanningError(ValueError):
    """当研究任务无法被安全、合规规划时抛出的强断言异常"""
    pass


@dataclass
class ResearchPlan:
    """结构化研究规划方案 (ResearchPlan Schema)"""
    objective: str
    symbols: List[str]
    date_range: Dict[str, str] = field(default_factory=lambda: {"start_date": "2024-01-01", "end_date": "2026-07-20"})
    required_tools: List[str] = field(default_factory=list)
    alpha_ids: List[str] = field(default_factory=list)
    benchmark_symbols: List[str] = field(default_factory=list)
    analysis_steps: List[Dict[str, Any]] = field(default_factory=list)
    integrity_requirements: Dict[str, Any] = field(default_factory=lambda: {
        "data_mode": "RESEARCH",
        "is_real": True,
        "reject_demo": True,
        "reject_naked_symbol": True,
        "pit_required": True,
        "lookahead_safe": True
    })
    evidence_requirements: Dict[str, Any] = field(default_factory=lambda: {
        "evidence_enabled": True,
        "hash_verification": True
    })
    expected_outputs: List[str] = field(default_factory=list)
    is_valid: bool = True
    planning_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "symbols": self.symbols,
            "date_range": self.date_range,
            "required_tools": self.required_tools,
            "alpha_ids": self.alpha_ids,
            "benchmark_symbols": self.benchmark_symbols,
            "analysis_steps": self.analysis_steps,
            "integrity_requirements": self.integrity_requirements,
            "evidence_requirements": self.evidence_requirements,
            "expected_outputs": self.expected_outputs,
            "is_valid": self.is_valid,
            "planning_error": self.planning_error
        }
