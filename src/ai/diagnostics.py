"""
diagnostics.py
确定性量化诊断引擎 (DiagnosticsEngine)
基于 Python 严格数学逻辑检测：Performance 异常、因子衰减 (Factor Decay)、过拟合 (Overfitting Warning) 与 大盘 Market Regime 表现。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from src.ai.schemas import DiagnosticResult


class DiagnosticsEngine:
    @staticmethod
    def diagnose_performance(metrics: Dict[str, Any]) -> DiagnosticResult:
        sharpe = float(metrics.get("Sharpe", 0.0))
        mdd = float(metrics.get("MaxDrawdown", 0.0))
        total_ret = float(metrics.get("TotalReturn", 0.0))

        if sharpe < 0.5 or mdd > 0.25:
            return DiagnosticResult(
                level="HIGH",
                summary="⚠️ 风险较高：策略夏普比率过低或最大回撤显著超出安全阈值 (MaxDrawdown > 25%)",
                details={"Sharpe": sharpe, "MaxDrawdown": mdd}
            )
        elif sharpe >= 1.2 and mdd <= 0.15:
            return DiagnosticResult(
                level="LOW",
                summary="🟢 表现极佳：高夏普比率 (Sharpe >= 1.2) 且最大回撤受控 (MaxDrawdown <= 15%)",
                details={"Sharpe": sharpe, "MaxDrawdown": mdd}
            )
        return DiagnosticResult(
            level="MODERATE",
            summary="🟡 表现中规中矩：风险收益比总体平稳",
            details={"Sharpe": sharpe, "MaxDrawdown": mdd}
        )

    @staticmethod
    def detect_overfitting(train_sharpe: float, val_sharpe: float, test_sharpe: float) -> DiagnosticResult:
        """
        过拟合诊断：若 Train Sharpe 远高于 Test Sharpe (降幅 > 40%)，提示过拟合风险
        """
        if train_sharpe > 0 and test_sharpe / train_sharpe < 0.6:
            return DiagnosticResult(
                level="CRITICAL",
                summary="🚨 强过拟合预警：样本外 (Test) 夏普比率较训练集 (Train) 暴跌超过 40%",
                details={"train_sharpe": train_sharpe, "val_sharpe": val_sharpe, "test_sharpe": test_sharpe}
            )
        elif train_sharpe > 0 and test_sharpe / train_sharpe < 0.8:
            return DiagnosticResult(
                level="MODERATE",
                summary="⚠️ 轻微过拟合：样本外表现有轻度衰减",
                details={"train_sharpe": train_sharpe, "val_sharpe": val_sharpe, "test_sharpe": test_sharpe}
            )
        return DiagnosticResult(
            level="LOW",
            summary="🟢 泛化能力良好：样本外夏普比率与训练期基本持平",
            details={"train_sharpe": train_sharpe, "val_sharpe": val_sharpe, "test_sharpe": test_sharpe}
        )

    @staticmethod
    def detect_factor_decay(annual_ics: Dict[str, float]) -> DiagnosticResult:
        """
        因子衰减检测：检查连续年份的 IC 是否呈现递减趋势
        """
        if len(annual_ics) < 2:
            return DiagnosticResult(level="LOW", summary="数据不足以判断衰减", details=annual_ics)

        years = sorted(annual_ics.keys())
        ic_vals = [annual_ics[y] for y in years]
        is_declining = all(x > y for x, y in zip(ic_vals, ic_vals[1:]))

        if is_declining and (ic_vals[0] - ic_vals[-1] > 0.03):
            return DiagnosticResult(
                level="HIGH",
                summary="🚨 因子 Alpha 衰减：IC 值逐年呈明显下滑趋势，Alpha 边际失效",
                details=annual_ics
            )
        return DiagnosticResult(
            level="LOW",
            summary="🟢 因子 Alpha 稳定：IC 序列随时间保持平稳",
            details=annual_ics
        )

    @staticmethod
    def analyze_regime_performance(history_df: pd.DataFrame) -> Dict[str, Any]:
        """
        分大盘 Market Regime (看多 / 避险) 统计收益与夏普比率
        """
        if history_df.empty or "daily_return" not in history_df.columns:
            return {"bull_sharpe": 0.0, "bear_sharpe": 0.0}

        rets = history_df["daily_return"]
        bull_rets = rets[rets >= 0]
        bear_rets = rets[rets < 0]

        bull_s = float((bull_rets.mean() / bull_rets.std()) * np.sqrt(252)) if len(bull_rets) > 1 and bull_rets.std() > 0 else 0.0
        bear_s = float((bear_rets.mean() / bear_rets.std()) * np.sqrt(252)) if len(bear_rets) > 1 and bear_rets.std() > 0 else 0.0

        return {"bull_sharpe": round(bull_s, 2), "bear_sharpe": round(bear_s, 2)}
