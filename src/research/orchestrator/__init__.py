"""
__init__.py
Multi-Agent Orchestration Package Exposing ResearchOrchestrator, ResearchContext, AgentResult, OrchestratorStatus
"""

from src.research.orchestrator.schema import ResearchContext, AgentResult, OrchestratorStatus
from src.research.orchestrator.agents import ResearchAgent, DataAgent, QuantAgent
from src.research.orchestrator.orchestrator import ResearchOrchestrator

__all__ = [
    "ResearchContext",
    "AgentResult",
    "OrchestratorStatus",
    "ResearchAgent",
    "DataAgent",
    "QuantAgent",
    "ResearchOrchestrator"
]
