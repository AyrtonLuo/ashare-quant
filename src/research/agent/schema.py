"""
schema.py
ReAct Research Agent 状态、步骤与最终研究结论契约模型
(AgentStep, AgentState, ResearchResult)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.research.planner.schema import ResearchPlan
from src.research.tools.base import ToolResult, ToolExecutionRecord


@dataclass
class AgentStep:
    """ReAct 单步链卡片 (Step in ReAct Loop)"""
    step_number: int
    thought: str
    action_tool: str
    action_kwargs: Dict[str, Any]
    observation: Optional[ToolResult] = None
    integrity_passed: bool = True
    step_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentState:
    """Agent 执行环内部状态 (State in ReAct Loop)"""
    run_id: str
    user_query: str
    plan: Optional[ResearchPlan] = None
    steps: List[AgentStep] = field(default_factory=list)
    is_finished: bool = False
    error: Optional[str] = None


@dataclass
class ResearchResult:
    """Agent 最终研究输出卡片 (Final Auditable Output)"""
    run_id: str
    user_query: str
    plan: ResearchPlan
    final_answer: str
    tool_execution_records: List[ToolExecutionRecord] = field(default_factory=list)
    evidences: List[Dict[str, Any]] = field(default_factory=list)
    is_real: bool = True
    data_mode: str = "RESEARCH"
    result_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "user_query": self.user_query,
            "plan": self.plan.to_dict() if self.plan else None,
            "final_answer": self.final_answer,
            "records_count": len(self.tool_execution_records),
            "evidences_count": len(self.evidences),
            "is_real": self.is_real,
            "data_mode": self.data_mode,
            "result_hash": self.result_hash
        }
