"""
orchestrator.py
ResearchOrchestrator 核心调度器:
1. 创建并维护 ResearchContext
2. 调度 ResearchAgent, DataAgent, QuantAgent
3. 收集并校验 ToolExecutionRecord 存证
4. 汇总最终 ResearchResult，绝不绕过 ToolRegistry 或 IntegrityGate
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.research.orchestrator.schema import ResearchContext, AgentResult, OrchestratorStatus
from src.research.orchestrator.agents import ResearchAgent, DataAgent, QuantAgent
from src.research.tools.registry import AgentToolRegistry
from src.research.agent import ResearchResult



class ResearchOrchestrator:
    """多 Agent 研究编排调度器 (ResearchOrchestrator)"""

    def __init__(self, tool_registry: Optional[AgentToolRegistry] = None):
        self.tool_registry = tool_registry or AgentToolRegistry()
        self.research_agent = ResearchAgent(tool_registry=self.tool_registry)
        self.data_agent = DataAgent(tool_registry=self.tool_registry)
        self.quant_agent = QuantAgent(tool_registry=self.tool_registry)

    def execute_research(
        self,
        query: str,
        symbols: Optional[List[str]] = None,
        alpha_ids: Optional[List[str]] = None,
        enable_parallel: bool = False
    ) -> ResearchContext:
        """主调度入口: 创建 Context -> 调度 Agent -> 汇总存证 -> 返回 Context"""
        if not query or not query.strip():
            context = ResearchContext(
                research_id=f"res_{uuid.uuid4().hex[:8]}",
                user_query=query or "",
                status=OrchestratorStatus.FAILED.value,
                errors=["Empty research request query"]
            )
            return context

        context = ResearchContext(
            research_id=f"res_{uuid.uuid4().hex[:8]}",
            user_query=query,
            active_agents=["RESEARCH_AGENT", "DATA_AGENT", "QUANT_AGENT"],
            status=OrchestratorStatus.RUNNING.value
        )

        context_data = {
            "symbols": symbols or ["600519.SH"],
            "alpha_ids": alpha_ids or ["MOM_20D", "VOL_20D"]
        }

        # 1. 调度 DataAgent
        data_res = self.data_agent.run(query, context_data)
        context.agent_results["DATA_AGENT"] = data_res
        context.tool_execution_records.extend(data_res.tool_execution_records)
        if data_res.errors:
            context.errors.extend(data_res.errors)

        # 2. 调度 QuantAgent
        quant_res = self.quant_agent.run(query, context_data)
        context.agent_results["QUANT_AGENT"] = quant_res
        context.tool_execution_records.extend(quant_res.tool_execution_records)
        if quant_res.errors:
            context.errors.extend(quant_res.errors)

        # 3. 调度 ResearchAgent
        res_agent_res = self.research_agent.run(query, context_data)
        context.agent_results["RESEARCH_AGENT"] = res_agent_res
        context.tool_execution_records.extend(res_agent_res.tool_execution_records)
        if res_agent_res.errors:
            context.errors.extend(res_agent_res.errors)

        # 4. 判断 Orchestrator 最终状态
        success_count = sum(1 for r in context.agent_results.values() if r.status == "SUCCESS")
        if success_count == len(context.agent_results):
            context.status = OrchestratorStatus.COMPLETED.value
        elif success_count > 0 or any(r.status == "PARTIAL" for r in context.agent_results.values()):
            context.status = OrchestratorStatus.PARTIAL.value
        else:
            context.status = OrchestratorStatus.FAILED.value

        return context
