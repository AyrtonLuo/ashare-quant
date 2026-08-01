"""
generate_daily_report.py
每日自动生成 AI Quant Daily Brief 报告 (reports/YYYY-MM-DD_daily_brief.md)
"""

import sys
import os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.ai.schemas import ResearchContext
from src.ai.report_generator import AutomatedReportGenerator
from src.runs.run_manager import RunManager


def main():
    rm = RunManager()
    today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
    rec = rm.start_run(run_id=f"job_brief_{today_str}", run_type="Report Run")

    try:
        ctx = ResearchContext(
            experiment_id=f"daily_brief_{today_str}",
            strategy_id="Daily_Quant_System_Brief",
            universe=["600519", "000001", "600690"],
            date_range=today_str,
            benchmark="000300",
            performance_metrics={"TotalReturnPct": "+0.62%", "Sharpe": 1.52, "MaxDrawdownPct": "12.80%"},
            decay_info={"annual_ics": {"2025": 0.065, "2026": 0.063}},
            overfitting_info={"train_sharpe": 1.6, "val_sharpe": 1.5, "test_sharpe": 1.52}
        )
        gen = AutomatedReportGenerator()
        filepath = gen.generate_report(ctx)
        rm.complete_run(rec, status="SUCCESS")
        print(f"✅ Daily AI Quant Brief Generated: {filepath}")
    except Exception as e:
        rm.complete_run(rec, status="FAILED", error=str(e))
        print(f"❌ Daily Brief Generation Failed: {e}")


if __name__ == "__main__":
    main()
