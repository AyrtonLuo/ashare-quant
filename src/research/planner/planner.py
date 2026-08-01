"""
planner.py
ResearchPlanner 确定性研究规划器 (Deterministic Research Planner)
负责将自然语言/结构化用户研究需求解析并校验为合规的 ResearchPlan。
绝对不直接调取 Data Provider，绝对不下发未注册 Tool 或 Alpha。
"""

import re
from typing import List, Dict, Any, Optional
from src.research.planner.schema import ResearchPlan, PlanningError
from src.research.tools.registry import AgentToolRegistry
from src.factors.alpha_zoo.registry import AlphaRegistry
from src.data.symbol_utils import normalize_ashare_code, CANONICAL_SYMBOL_NAMES


class ResearchPlanner:
    """确定性研究规划器"""

    # 常见标的映射表
    NAME_SYMBOL_MAP = {
        "贵州茅台": "600519.SH",
        "平安银行": "000001.SZ",
        "招商银行": "600036.SH",
        "上证指数": "000001.SH",
        "沪深300": "000300.SH",
        "中证1000": "000852.SH"
    }

    @classmethod
    def create_plan(cls, user_request: str, mode: str = "RESEARCH MODE") -> ResearchPlan:
        """
        解析自然语言请求，生成结构化 ResearchPlan
        包含严格的 Schema Validation, Canonical Symbol 校验, Tool/Alpha 校验与安全门控规则。
        """
        req_clean = user_request.strip()

        # 1. 不可执行 / 违规请求阻断
        if any(unsupported in req_clean for unsupported in ["预测明天涨停", "自动实盘下单", "删除数据", "修改配置"]):
            return ResearchPlan(
                objective=req_clean,
                symbols=[],
                is_valid=False,
                planning_error=f"不可执行的研究请求：[{req_clean}] 超出安全研究规划边界"
            )

        # 2. Demo / Mock 违规请求阻断
        if mode == "RESEARCH MODE" and any(d_kw in req_clean.lower() for d_kw in ["demo", "mock", "模拟假数据", "硬编码价格"]):
            return ResearchPlan(
                objective=req_clean,
                symbols=[],
                is_valid=False,
                planning_error="RESEARCH MODE 严禁请求 Demo / Mock 或硬编码假行情数据"
            )

        # 3. 裸代码 "000001" 阻断
        if re.search(r'\b000001\b(?![\.\w])', req_clean):
            return ResearchPlan(
                objective=req_clean,
                symbols=[],
                is_valid=False,
                planning_error="拒绝裸代码 '000001'，必须明确声明 '000001.SH' (上证指数) 或 '000001.SZ' (平安银行)"
            )

        # 4. 解析 Canonical Symbol
        symbols = cls._extract_symbols(req_clean)
        if not symbols:
            # 默认补全规范标的 (如 600519.SH)
            symbols = ["600519.SH"]

        # 5. 解析所需 Tool 与 Alpha
        required_tools = cls._resolve_tools(req_clean)
        alpha_ids = cls._resolve_alphas(req_clean)

        # 6. 校验 Tool 存在性
        for t_name in required_tools:
            try:
                AgentToolRegistry.get(t_name)
            except KeyError:
                return ResearchPlan(
                    objective=req_clean,
                    symbols=symbols,
                    is_valid=False,
                    planning_error=f"规划失败：规划的工具 [{t_name}] 未在 AgentToolRegistry 注册"
                )

        # 7. 校验 Alpha 存在性
        for a_id in alpha_ids:
            try:
                AlphaRegistry.get(a_id)
            except KeyError:
                return ResearchPlan(
                    objective=req_clean,
                    symbols=symbols,
                    is_valid=False,
                    planning_error=f"规划失败：规划的 Alpha [{a_id}] 未在 AlphaRegistry 注册"
                )

        # 8. 生成结构化步骤 (Analysis Steps)
        analysis_steps = []
        step_idx = 1

        if "get_market_quote" in required_tools:
            for sym in symbols:
                analysis_steps.append({
                    "step_id": step_idx,
                    "tool_name": "get_market_quote",
                    "kwargs": {"symbol": sym},
                    "purpose": f"获取标的 [{sym}] 的最新真实 MarketDataContract 行情"
                })
                step_idx += 1

        if "compute_factor" in required_tools and alpha_ids:
            for a_id in alpha_ids:
                analysis_steps.append({
                    "step_id": step_idx,
                    "tool_name": "compute_factor",
                    "kwargs": {"alpha_id": a_id, "symbols": symbols},
                    "purpose": f"计算因子 [{a_id}] 并生成 Evidence 存证"
                })
                step_idx += 1

        if "run_backtest" in required_tools:
            analysis_steps.append({
                "step_id": step_idx,
                "tool_name": "run_backtest",
                "kwargs": {"symbols": symbols},
                "purpose": f"对标的列表 {symbols} 运行无未来函数历史回测"
            })
            step_idx += 1

        return ResearchPlan(
            objective=req_clean,
            symbols=symbols,
            required_tools=required_tools,
            alpha_ids=alpha_ids,
            benchmark_symbols=["000300.SH"] if "000300.SH" not in symbols else ["000001.SH"],
            analysis_steps=analysis_steps,
            expected_outputs=[
                "MarketDataContract 快照",
                "AlphaEvidenceRecord 存证卡片",
                "包含 Sharpe/Drawdown 的回测归因报告"
            ],
            is_valid=True,
            planning_error=None
        )

    @classmethod
    def _extract_symbols(cls, text: str) -> List[str]:
        found = []

        # 匹配中文名称
        for name, sym in cls.NAME_SYMBOL_MAP.items():
            if name in text and sym not in found:
                found.append(sym)

        # 匹配后缀代码 (000001.SH, 600519.SH, 000001.SZ)
        matches = re.findall(r'\b\d{6}\.(?:SH|SZ)\b', text, re.IGNORECASE)
        for m in matches:
            canonical = m.upper()
            if canonical not in found:
                found.append(canonical)

        return found

    @classmethod
    def _resolve_tools(cls, text: str) -> List[str]:
        tools = ["get_market_quote"]
        txt_l = text.lower()

        if any(kw in text for kw in ["因子", "动量", "反转", "波动", "换手", "EP", "alpha", "Alpha"]):
            tools.append("compute_factor")
        if any(kw in text for kw in ["回测", "收益", "夏普", "回撤", "绩效"]):
            tools.append("run_backtest")
        if any(kw in text for kw in ["风控", "压力测试", "暴跌", "Barra"]):
            tools.append("run_stress_test")

        return list(dict.fromkeys(tools))

    @classmethod
    def _resolve_alphas(cls, text: str) -> List[str]:
        alphas = []
        txt = text.upper()

        if "5D" in txt and "动量" in text:
            alphas.append("MOM_5D")
        if "20D" in txt or "动量" in text or "过去一月" in text or "过去一个月" in text:
            alphas.append("MOM_20D")
        if "60D" in txt or "过去一季" in text:
            alphas.append("MOM_60D")
        if "反转" in text or "均值回归" in text:
            alphas.append("REV_20D")
        if "波动" in text:
            alphas.append("VOL_20D")
        if "换手" in text or "流动性" in text:
            alphas.append("TURNOVER_20D")
        if "EP" in txt or "市盈率" in text or "估值" in text:
            alphas.append("EP_TTM")

        if not alphas and ("因子" in text or "Alpha" in text):
            alphas.append("MOM_20D")

        return list(dict.fromkeys(alphas))
