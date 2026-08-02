"""
agents.py
多 Agent Orchestration 逻辑角色定义:
1. ResearchAgent: 规划、假设拆解与综合推理 (复用 ReActResearchAgent)
2. DataAgent: 依赖行情与基本面数据发现 (通过 AgentToolRegistry 鉴权)
3. QuantAgent: 因子检索与 Alpha 因子计算 (通过 AlphaRegistry 与 AgentToolRegistry)
"""

from typing import Dict, Any, List, Optional
from app import get_services
from src.research.orchestrator.schema import AgentResult
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.base import ToolExecutionContext
from src.research.agent import ReActResearchAgent, ResearchResult
from src.research.planner import ResearchPlanner
from src.factors.alpha_zoo import AlphaRegistry




class BaseOrchestratorAgent:
    def __init__(self, agent_id: str, role: str, tool_registry: Optional[AgentToolRegistry] = None):
        self.agent_id = agent_id
        self.role = role
        self.tool_registry = tool_registry or AgentToolRegistry()

    def run(self, query: str, context_data: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class ResearchAgent(BaseOrchestratorAgent):

    """ResearchAgent: 研究规划与假设分解"""
    def __init__(self, agent_id: str = "research_agent_01", tool_registry: Optional[AgentToolRegistry] = None):
        super().__init__(agent_id=agent_id, role="RESEARCH_AGENT", tool_registry=tool_registry)
        self.react_agent = ReActResearchAgent(mode="RESEARCH MODE")
        self.planner = ResearchPlanner()

    def run(self, query: str, context_data: Dict[str, Any]) -> AgentResult:
        try:
            plan = self.planner.create_plan(query)
            res = self.react_agent.run(query)
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_role=self.role,
                status="SUCCESS",
                summary=f"Research Plan Objective: {plan.objective}. ReAct Analysis: {getattr(res, 'final_answer', str(res))}",
                evidence=getattr(res, "evidences", []),
                tool_execution_records=getattr(res, "tool_execution_records", []),
                errors=[]
            )
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                agent_role=self.role,
                status="FAILED",
                summary=f"ResearchAgent execution failed: {str(e)}",
                evidence=[],
                tool_execution_records=[],
                errors=[str(e)]
            )


class DataAgent(BaseOrchestratorAgent):

    """DataAgent: 行情与基本面数据检索 (100% 经过 AgentToolRegistry 门控)"""
    def __init__(self, agent_id: str = "data_agent_01", tool_registry: Optional[AgentToolRegistry] = None):
        super().__init__(agent_id=agent_id, role="DATA_AGENT", tool_registry=tool_registry)

    def run(self, query: str, context_data: Dict[str, Any]) -> AgentResult:
        evidence = []
        errors = []
        symbols = context_data.get("symbols", ["600519.SH"])
        services = get_services("RESEARCH MODE")
        exec_ctx = ToolExecutionContext(run_id=f"data_{self.agent_id}", data_mode="RESEARCH", services=services)
        rec_start = len(AgentToolRegistry.get_execution_records())

        for sym in symbols:
            # 1. 行情报价
            try:
                q_res = AgentToolRegistry.execute("get_market_quote", context=exec_ctx, symbol=sym)
                if q_res.success:
                    evidence.append({"symbol": sym, "type": "quote", "data": q_res.data})
                else:
                    errors.append(q_res.error or f"Failed quote for {sym}")
            except Exception as e:
                errors.append(str(e))

            # 2. 历史价格 K 线
            try:
                h_res = AgentToolRegistry.execute("get_historical_prices", context=exec_ctx, symbol=sym, start_date="2024-01-01", end_date="2025-01-01")
                if h_res.success:
                    evidence.append({"symbol": sym, "type": "historical", "data": h_res.data})
                else:
                    errors.append(h_res.error or f"Failed history for {sym}")
            except Exception as e:
                errors.append(str(e))

        records = AgentToolRegistry.get_execution_records()[rec_start:]
        status = "SUCCESS" if not errors else ("PARTIAL" if evidence else "FAILED")
        return AgentResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=status,
            summary=f"Retrieved market data for {len(symbols)} symbols",
            evidence=evidence,
            tool_execution_records=records,
            errors=errors
        )


class QuantAgent(BaseOrchestratorAgent):
    """QuantAgent: 因子检索与 Alpha 分析 (使用 AlphaRegistry 与 AgentToolRegistry)"""
    def __init__(self, agent_id: str = "quant_agent_01", tool_registry: Optional[AgentToolRegistry] = None):
        super().__init__(agent_id=agent_id, role="QUANT_AGENT", tool_registry=tool_registry)

    def run(self, query: str, context_data: Dict[str, Any]) -> AgentResult:
        evidence = []
        errors = []
        alpha_ids = context_data.get("alpha_ids", ["MOM_20D", "VOL_20D"])
        services = get_services("RESEARCH MODE")
        exec_ctx = ToolExecutionContext(run_id=f"quant_{self.agent_id}", data_mode="RESEARCH", services=services)
        rec_start = len(AgentToolRegistry.get_execution_records())

        for alpha_id in alpha_ids:
            try:
                f_res = AgentToolRegistry.execute("compute_factor", context=exec_ctx, factor_name=alpha_id, symbol="600519.SH")
                if f_res.success:
                    evidence.append({"alpha_id": alpha_id, "result": f_res.data})
                else:
                    errors.append(f_res.error or f"Factor computation failed for {alpha_id}")
            except Exception as e:
                errors.append(str(e))

        records = AgentToolRegistry.get_execution_records()[rec_start:]
        status = "SUCCESS" if not errors else ("PARTIAL" if evidence else "FAILED")
        return AgentResult(
            agent_id=self.agent_id,
            agent_role=self.role,
            status=status,
            summary=f"Computed {len(evidence)} alpha factor(s)",
            evidence=evidence,
            tool_execution_records=records,
            errors=errors
        )





