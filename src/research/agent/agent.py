"""
agent.py
ReActResearchAgent 交互式研究 Agent 实现 (ReAct Loop)
工作流：PLAN -> SELECT TOOL -> EXECUTE TOOL -> OBSERVE -> INTEGRITY CHECK -> EVIDENCE -> NEXT -> FINAL ANSWER
所有数据访问 100% 经过 AgentToolRegistry，严禁绕过工具层访问底层 Provider 或裸 DataFrame。
"""

import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.research.planner import ResearchPlanner, ResearchPlan
from src.research.tools.registry import AgentToolRegistry
from src.research.tools.base import ToolExecutionContext, ToolResult, ToolPermission
from src.research.agent.schema import AgentStep, AgentState, ResearchResult


class ReActResearchAgent:
    """ReAct 量化研究 Agent"""

    def __init__(self, mode: str = "RESEARCH MODE", permissions: Optional[set] = None):
        self.mode = mode
        self.permissions = permissions or {
            ToolPermission.READ_ONLY,
            ToolPermission.RESEARCH,
            ToolPermission.BACKTEST,
            ToolPermission.PORTFOLIO
        }

    def run(self, user_query: str, services: Optional[Dict[str, Any]] = None) -> ResearchResult:
        """
        执行 ReAct 闭环流程并输出只读归因卡片 ResearchResult
        """
        run_id = f"react_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 1. PLAN 阶段 (通过确定性 ResearchPlanner)
        plan = ResearchPlanner.create_plan(user_query, mode=self.mode)

        if not plan.is_valid:
            return ResearchResult(
                run_id=run_id,
                user_query=user_query,
                plan=plan,
                final_answer=f"研究规划被阻断: {plan.planning_error}",
                tool_execution_records=[],
                evidences=[],
                is_real=(self.mode == "RESEARCH MODE"),
                data_mode="RESEARCH" if self.mode == "RESEARCH MODE" else "DEMO",
                result_hash=hashlib.sha256(f"FAILED|{plan.planning_error}".encode("utf-8")).hexdigest()[:16]
            )

        # 构建工具执行上下文
        context = ToolExecutionContext(
            mode=self.mode,
            user_request=user_query,
            run_id=run_id,
            data_mode="RESEARCH" if self.mode == "RESEARCH MODE" else "DEMO",
            permissions=self.permissions,
            evidence_enabled=True,
            services=services or {}
        )

        steps: List[AgentStep] = []
        collected_evidences = []

        # 2. SELECT TOOL -> EXECUTE -> OBSERVE -> INTEGRITY CHECK 循环
        for step_info in plan.analysis_steps:
            step_num = step_info["step_id"]
            tool_name = step_info["tool_name"]
            tool_kwargs = step_info["kwargs"]
            purpose = step_info["purpose"]

            thought = f"步骤 {step_num}: 目标是在 [{self.mode}] 下调用 [{tool_name}]，用途: {purpose}"

            # 统一通过 AgentToolRegistry 派发工具 (绝不直调 Provider/DataFrame)
            tool_res = AgentToolRegistry.execute(tool_name, context, **tool_kwargs)

            # 收集 Evidence 证明
            if tool_res.evidence:
                collected_evidences.append(tool_res.evidence)

            step_record = AgentStep(
                step_number=step_num,
                thought=thought,
                action_tool=tool_name,
                action_kwargs=tool_kwargs,
                observation=tool_res,
                integrity_passed=tool_res.success
            )
            steps.append(step_record)

            # 强中断检查：若 API / Integrity Gate 判定数据不可用，直接记录不可用状态并提示
            if not tool_res.success and tool_res.error == "DATA_UNAVAILABLE":
                break

        # 3. FINAL ANSWER 渲染阶段
        records = [r for r in AgentToolRegistry.get_execution_records() if r.run_id == run_id]

        summary_lines = [
            f"### ReAct Research Agent 报告 (Run ID: {run_id})",
            f"**研究需求**: {user_query}",
            f"**数据模式**: {context.data_mode} (Real Data: {context.data_mode == 'RESEARCH'})",
            f"**规划标的**: {', '.join(plan.symbols)}",
            f"**已执行步骤数**: {len(steps)} / {len(plan.analysis_steps)}",
            "\n#### 步骤卡片摘要:"
        ]

        for s in steps:
            status_tag = "✅ SUCCESS" if s.integrity_passed else f"❌ FAILED ({s.observation.error if s.observation else 'Unknown'})"
            summary_lines.append(f"- **Step {s.step_number}** [{s.action_tool}]: {status_tag}")

        final_ans = "\n".join(summary_lines)
        res_hash = hashlib.sha256(f"{run_id}|{final_ans}".encode("utf-8")).hexdigest()[:16]

        return ResearchResult(
            run_id=run_id,
            user_query=user_query,
            plan=plan,
            final_answer=final_ans,
            tool_execution_records=records,
            evidences=collected_evidences,
            is_real=(self.mode == "RESEARCH MODE"),
            data_mode="RESEARCH" if self.mode == "RESEARCH MODE" else "DEMO",
            result_hash=res_hash
        )
