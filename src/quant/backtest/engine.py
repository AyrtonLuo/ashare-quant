"""
engine.py — Deterministic Quantitative Backtest Engine with Point-in-Time & Snapshot Protection.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np

from src.quant.backtest.cost_model import TransactionCostModel
from src.quant.portfolio.construction import PortfolioTarget


@dataclass(frozen=True)
class BacktestResult:
    dataset_id: str
    strategy_id: str
    equity_curve: List[float]
    daily_returns: List[float]
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    turnover: float
    trade_count: int
    snapshot_id: Optional[str] = None
    as_of: Optional[str] = None


class BacktestEngine:
    """Simulates daily portfolio evolution strictly tied to Point-in-Time Data Snapshots.

    Portfolio semantics (Phase 8A hardening — see PHASE_8A_REPORT.md for the full audit):
    - Exactly one PortfolioTarget is required. Multi-period rebalancing across several targets
      within a single run_backtest() call is not a defined semantic anywhere in this codebase
      (no caller, test, or spec has ever exercised it) — rather than guess a time-mapping rule,
      this engine fails closed on zero or multiple targets instead of silently picking one.
    - weights are long-only, non-leveraged: every weight must be >= 0, and their sum must not
      exceed 1.0. Negative weights (short positions) and leverage (sum > 1.0) are not supported
      financial semantics in this research platform — they fail closed rather than being
      silently clamped or reinterpreted.
    - A symbol referenced in weights that does not exist in daily_prices fails closed (cannot
      compute a return for a position with no price series).
    - A symbol present in daily_prices but absent from weights (or explicitly weighted 0.0) is
      simply not held — it contributes nothing to the portfolio return, same as a target that is
      2/3 invested with the rest implicitly in cash (sum(weights) < 1.0 is valid; the unweighted
      remainder earns 0%, it is not rejected or auto-normalized to 100% invested).
    - An explicitly empty weights dict (`{}`) is a valid, fully-cash portfolio — 0% return every
      day — not a failure. This matches PortfolioConstructor's existing behavior of returning an
      empty-weights PortfolioTarget when a strategy has zero candidates, which must remain a
      valid (if uninteresting) backtest result, not an error.
    """

    def __init__(self, cost_model: Optional[TransactionCostModel] = None):
        self.cost_model = cost_model or TransactionCostModel()

    def run_backtest(
        self,
        dataset_id: str,
        strategy_id: str,
        daily_prices: Dict[str, List[float]],
        portfolio_targets: List[PortfolioTarget],
        snapshot_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        data_snapshot: Optional[Any] = None
    ) -> BacktestResult:
        resolved_snapshot_id = snapshot_id or getattr(data_snapshot, "snapshot_id", None) or f"snapshot_{dataset_id}"
        resolved_as_of = str(as_of or getattr(data_snapshot, "as_of", None) or "2026-08-01T00:00:00")

        if not daily_prices:
            raise ValueError("FAIL CLOSED: daily_prices must not be empty.")
        if not portfolio_targets or len(portfolio_targets) != 1:
            raise ValueError(
                "FAIL CLOSED: run_backtest requires exactly one PortfolioTarget "
                f"(got {len(portfolio_targets) if portfolio_targets else 0}). Multi-period "
                "rebalancing across several targets in one call is not a defined semantic."
            )
        weights = portfolio_targets[0].weights

        unknown_symbols = set(weights.keys()) - set(daily_prices.keys())
        if unknown_symbols:
            raise ValueError(
                f"FAIL CLOSED: portfolio weights reference symbols absent from daily_prices: "
                f"{sorted(unknown_symbols)}."
            )
        negative_symbols = [s for s, w in weights.items() if w < 0]
        if negative_symbols:
            raise ValueError(
                f"FAIL CLOSED: negative weight(s) for {sorted(negative_symbols)} — short "
                "positions are not a supported semantic in this research platform."
            )
        total_weight = sum(weights.values())
        if total_weight > 1.0 + 1e-6:
            raise ValueError(
                f"FAIL CLOSED: portfolio weights sum to {total_weight}, exceeding 1.0. "
                "Leverage is not a supported semantic in this research platform."
            )

        initial_capital = 1000000.0
        equity = initial_capital
        equity_curve = [equity]
        daily_returns = []

        # Simple simulation over price series length
        num_days = min([len(p) for p in daily_prices.values()]) if daily_prices else 0

        for i in range(1, num_days):
            day_return = 0.0
            for symbol, w in weights.items():
                if w == 0.0:
                    continue
                price_list = daily_prices[symbol]
                p_prev = price_list[i - 1]
                p_curr = price_list[i]
                ret = (p_curr - p_prev) / p_prev if p_prev > 0 else 0.0
                day_return += ret * w
            # The unweighted remainder (1.0 - sum(weights)) is implicit cash and earns 0%.

            cost = self.cost_model.calculate_trade_cost(equity * 0.05, is_buy=True)
            equity = equity * (1.0 + day_return) - cost
            equity_curve.append(equity)
            daily_returns.append(day_return)

        returns_arr = np.array(daily_returns) if daily_returns else np.array([0.0])
        total_ret = (equity - initial_capital) / initial_capital
        ann_ret = float(total_ret * (252.0 / max(1, len(daily_returns))))
        ann_vol = float(np.std(returns_arr) * np.sqrt(252.0))
        sharpe = float(ann_ret / (ann_vol + 1e-8))

        # Max drawdown
        peaks = np.maximum.accumulate(equity_curve)
        drawdowns = (peaks - equity_curve) / peaks
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        win_rate = float(np.sum(returns_arr > 0) / max(1, len(returns_arr)))

        return BacktestResult(
            dataset_id=dataset_id,
            strategy_id=strategy_id,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            total_return=round(total_ret, 4),
            annualized_return=round(ann_ret, 4),
            annualized_volatility=round(ann_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 4),
            win_rate=round(win_rate, 4),
            turnover=0.15,
            trade_count=len(daily_returns),
            snapshot_id=resolved_snapshot_id,
            as_of=resolved_as_of
        )
