"""
decision_logger.py
调仓决策日志与 Markdown 决策报告生成器 (DecisionAuditLog)
生成形如 reports/YYYY-MM-DD_rebalance.md 的决策日志。
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger("decision_logger")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")


class DecisionAuditLog:
    def __init__(self, reports_dir: str = REPORTS_DIR):
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def log_decision(
        self,
        timestamp: str,
        strategy_id: str,
        target_weights: Dict[str, float],
        risk_info: Dict[str, Any],
        orders: List[Dict[str, Any]],
        portfolio_before: Dict[str, Any],
        portfolio_after: Dict[str, Any]
    ) -> str:
        """
        生成 Markdown 决策日志文件，返回文件路径
        """
        date_str = str(timestamp)[:10]
        filepath = os.path.join(self.reports_dir, f"{date_str}_rebalance.md")

        lines = [
            f"# 📋 Rebalance Decision Audit Log",
            f"",
            f"**Strategy**: `{strategy_id}`",
            f"**Timestamp**: `{timestamp}`",
            f"**Market Regime**: `{risk_info.get('regime', 'N/A')}`",
            f"**Allowed Equity Cap**: `{risk_info.get('equity_cap_pct', 100.0)}%`",
            f"",
            f"## 1. 🎯 Target Portfolio Weights",
            f"| Symbol | Target Weight |",
            f"| :--- | :---: |"
        ]

        for sym, w in target_weights.items():
            lines.append(f"| `{sym}` | `{w*100:.2f}%` |")

        lines.extend([
            f"",
            f"## 2. ⚡ Executed Orders",
            f"| Order ID | Symbol | Side | Quantity | Price | Status | Reason |",
            f"| :--- | :--- | :--- | :---: | :---: | :--- | :--- |"
        ])

        for o in orders:
            lines.append(f"| `{o.get('order_id', '-')}` | `{o.get('symbol', '-')}` | `{o.get('side', '-')}` | `{o.get('quantity', 0)}` | ¥`{o.get('price', 0.0):.2f}` | `{o.get('status', '-')}` | `{o.get('reason', 'OK')}` |")

        lines.extend([
            f"",
            f"## 3. 💼 Portfolio Snapshot Change",
            f"- **Equity Before**: ¥`{portfolio_before.get('total_equity', 0.0):,.2f}` | **Cash Before**: ¥`{portfolio_before.get('cash', 0.0):,.2f}`",
            f"- **Equity After**: ¥`{portfolio_after.get('total_equity', 0.0):,.2f}` | **Cash After**: ¥`{portfolio_after.get('cash', 0.0):,.2f}`",
            f"- **Market Value After**: ¥`{portfolio_after.get('market_value', 0.0):,.2f}`",
            f""
        ])

        content = "\n".join(lines)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"写入决策日志 {filepath} 异常 ({e})")

        return filepath
