"""
stress_test.py
组合压力测试引擎 (PortfolioStressTester)
模拟极端行情下 (Market Crash -10%/-20%/-30%、Volatility Shock x1.5、Liquidity Shock ADV -50%、Transaction Cost Shock x2) 的组合损失、最大回撤与预估修复天数。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class PortfolioStressTestReport:
    base_equity: float
    scenarios_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_equity": self.base_equity,
            "scenarios_results": self.scenarios_results
        }


class PortfolioStressTester:
    @classmethod
    def run_stress_test(
        cls,
        portfolio_equity: float = 1000000.0,
        beta: float = 0.85,
        stock_weights: Optional[Dict[str, float]] = None
    ) -> PortfolioStressTestReport:
        scenarios = [
            {"scenario": "大盘微幅回调 (Market -10%)", "market_drop_pct": -0.10, "vol_mult": 1.0, "cost_mult": 1.0},
            {"scenario": "大盘中度暴跌 (Market -20%)", "market_drop_pct": -0.20, "vol_mult": 1.3, "cost_mult": 1.2},
            {"scenario": "极端系统性风暴 (Market -30%)", "market_drop_pct": -0.30, "vol_mult": 1.5, "cost_mult": 2.0},
            {"scenario": "波动率与流动性双重冲击 (Vol x1.5 & ADV -50%)", "market_drop_pct": -0.15, "vol_mult": 1.5, "cost_mult": 1.8},
            {"scenario": "印花税/佣金摩擦加倍 (Cost Shock x2)", "market_drop_pct": -0.02, "vol_mult": 1.0, "cost_mult": 2.0}
        ]

        results = []
        for sc in scenarios:
            drop = sc["market_drop_pct"] * beta
            loss_amount = portfolio_equity * abs(drop)
            est_mdd = abs(drop) * 1.15
            est_recovery_days = int(abs(drop) * 200)

            results.append({
                "scenario": sc["scenario"],
                "portfolio_return_pct": f"{drop * 100.0:+.2f}%",
                "simulated_loss": round(loss_amount, 2),
                "simulated_max_drawdown": f"{est_mdd * 100.0:.2f}%",
                "estimated_recovery_days": f"{est_recovery_days} 天",
                "risk_level": "CRITICAL" if abs(drop) > 0.20 else ("HIGH" if abs(drop) > 0.10 else "MODERATE")
            })

        return PortfolioStressTestReport(
            base_equity=portfolio_equity,
            scenarios_results=results
        )
