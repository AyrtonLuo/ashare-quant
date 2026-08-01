"""
skills_registry.py
SkillRegistry 与 ResearchSkill 技能注册表
为 ReAct Research Agent 提供标准化的分析 Workflow 技能模版。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ResearchSkill:
    """研究技能模板定义"""
    skill_id: str
    name: str
    description: str
    required_tools: List[str]
    required_alphas: List[str] = field(default_factory=list)


class SkillRegistry:
    """Skill 注册表"""
    _skills: Dict[str, ResearchSkill] = {}

    @classmethod
    def register(cls, skill: ResearchSkill):
        cls._skills[skill.skill_id] = skill

    @classmethod
    def get(cls, skill_id: str) -> Optional[ResearchSkill]:
        return cls._skills.get(skill_id)

    @classmethod
    def list_all(cls) -> List[ResearchSkill]:
        return list(cls._skills.values())


# 注册默认技能
SkillRegistry.register(ResearchSkill(
    skill_id="MOMENTUM_ANALYSIS",
    name="动量因子趋势分析技能",
    description="对指定标的评估 MOM_5D / MOM_20D / MOM_60D 多周期动量强弱",
    required_tools=["get_market_quote", "compute_factor"],
    required_alphas=["MOM_5D", "MOM_20D", "MOM_60D"]
))

SkillRegistry.register(ResearchSkill(
    skill_id="FACTOR_BACKTEST",
    name="因子策略回测归因技能",
    description="运行前复权无未来函数策略历史回测并提取 Sharpe / Drawdown",
    required_tools=["compute_factor", "run_backtest"],
    required_alphas=["MOM_20D", "REV_20D"]
))

SkillRegistry.register(ResearchSkill(
    skill_id="RISK_STRESS_TEST",
    name="组合风控与压力测试技能",
    description="评估申万行业/Barra 风格暴露度并运行大盘暴跌 -30% 压力测试",
    required_tools=["get_portfolio_exposure", "run_stress_test"]
))
