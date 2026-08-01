"""
report_generator.py
自动化量化研报生成器 (AutomatedReportGenerator)
整合 ResearchContext、DiagnosticsEngine 和 LLMProvider，自动输出 Markdown 研报至 reports/experiment_xxx_ai.md。
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from src.ai.schemas import ResearchContext
from src.ai.diagnostics import DiagnosticsEngine
from src.ai.provider import LLMProvider, MockLLMProvider

logger = logging.getLogger("report_generator")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")


class AutomatedReportGenerator:
    def __init__(self, provider: Optional[LLMProvider] = None, reports_dir: str = REPORTS_DIR):
        self.provider = provider or MockLLMProvider()
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_report(self, context: ResearchContext) -> str:
        """
        根据结构化 ResearchContext 生成全套 Markdown 研报并落盘
        """
        perf_diag = DiagnosticsEngine.diagnose_performance(context.performance_metrics)
        decay_diag = DiagnosticsEngine.detect_factor_decay(context.decay_info.get("annual_ics", {}))

        train_s = context.overfitting_info.get("train_sharpe", 1.5)
        val_s = context.overfitting_info.get("val_sharpe", 1.2)
        test_s = context.overfitting_info.get("test_sharpe", float(context.performance_metrics.get("Sharpe", 1.0)))
        overfit_diag = DiagnosticsEngine.detect_overfitting(train_s, val_s, test_s)

        prompt = f"""
请分析量化实验 {context.experiment_id}:
- 策略: {context.strategy_id}
- 回测区间: {context.date_range}
- 策略收益: {context.performance_metrics.get('TotalReturnPct', '0%')} | 夏普比率: {context.performance_metrics.get('Sharpe', 0.0)} | 最大回撤: {context.performance_metrics.get('MaxDrawdownPct', '0%')}
- 诊断总结: {perf_diag.summary}
- 过拟合判定: {overfit_diag.summary}
- 因子衰减判定: {decay_diag.summary}
"""
        ai_conclusion = self.provider.generate(prompt)

        lines = [
            f"# 📊 Quant Research Report: `{context.experiment_id}`",
            f"",
            f"**Strategy ID**: `{context.strategy_id}` | **Benchmark**: `{context.benchmark}` | **Period**: `{context.date_range}`",
            f"",
            f"## 1. 🎯 Executive Performance Summary",
            f"| Metric | Value | Benchmark ({context.benchmark}) |",
            f"| :--- | :---: | :---: |",
            f"| **Total Return** | `{context.performance_metrics.get('TotalReturnPct', '0.0%')}` | `{context.performance_metrics.get('BenchmarkReturnPct', '0.0%')}` |",
            f"| **Sharpe Ratio** | `{context.performance_metrics.get('Sharpe', 0.0)}` | - |",
            f"| **Max Drawdown** | `{context.performance_metrics.get('MaxDrawdownPct', '0.0%')}` | - |",
            f"| **Volatility** | `{context.performance_metrics.get('VolatilityPct', '0.0%')}` | - |",
            f"",
            f"## 2. 🔍 Quantitative Diagnostics Engine",
            f"- **Performance Risk**: {perf_diag.summary}",
            f"- **Overfitting Warning**: {overfit_diag.summary}",
            f"- **Factor Decay Status**: {decay_diag.summary}",
            f"",
            f"## 3. 🤖 AI Research Conclusion & Insights",
            f"{ai_conclusion}",
            f"",
            f"## 4. ⚠️ Research Limitations & Disclaimers",
            f"- AI 研报基于确凿 Python 计算数据总结，严格禁止直接自动下单。",
            f""
        ]

        content = "\n".join(lines)
        filepath = os.path.join(self.reports_dir, f"{context.experiment_id}_ai.md")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            json_path = os.path.join(self.reports_dir, f"{context.experiment_id}_ai.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(context.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入 AI 研报报告失败 ({e})")

        return filepath
