"""
schema.py
Multi-Agent Orchestration 数据模型体系 (ResearchContext, AgentResult, OrchestratorStatus)
提供强类型、可序列化、可测试的 Agent 交互与上下文契约。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from src.research.tools.base import ToolExecutionRecord


class OrchestratorStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


@dataclass
class AgentResult:
    """Agent 执行结果强契约结构体 (AgentResult)"""
    agent_id: str
    agent_role: str
    status: str                                    # SUCCESS / FAILED / PARTIAL
    summary: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tool_execution_records: List[ToolExecutionRecord] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "tool_execution_records": [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in self.tool_execution_records],
            "errors": self.errors,
            "created_at": self.created_at
        }


@dataclass
class ResearchContext:
    """多 Agent 研究上下文模型 (ResearchContext)"""
    research_id: str
    user_query: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    active_agents: List[str] = field(default_factory=list)
    agent_results: Dict[str, AgentResult] = field(default_factory=dict)
    tool_execution_records: List[ToolExecutionRecord] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = OrchestratorStatus.CREATED.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "research_id": self.research_id,
            "user_query": self.user_query,
            "created_at": self.created_at,
            "active_agents": self.active_agents,
            "agent_results": {k: v.to_dict() for k, v in self.agent_results.items()},
            "tool_execution_records": [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in self.tool_execution_records],
            "errors": self.errors,
            "status": self.status
        }
