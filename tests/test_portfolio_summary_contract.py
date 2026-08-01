"""
test_portfolio_summary_contract.py
Regression tests for PortfolioService and PaperAccount Summary Data Contract
Verifies that total_return_pct and all essential keys are ALWAYS present, handling empty portfolios, missing market data, and zero trades gracefully.
"""

import pytest
import pandas as pd
from src.execution.paper_trader import PaperAccount
from src.services.portfolio_service import PortfolioService


def test_normal_portfolio_summary():
    account = PaperAccount(initial_capital=1000000.0)
    account.reset_account(capital=1000000.0)
    svc = PortfolioService(account)
    summary = svc.get_portfolio_summary({"600519": 1450.0})

    assert "total_return_pct" in summary
    assert "pnl_pct" in summary
    assert "total_equity" in summary
    assert "cash" in summary
    assert "market_value" in summary
    assert summary["total_return_pct"] == 0.0
    assert summary["total_equity"] == 1000000.0


def test_empty_portfolio_summary():
    svc = PortfolioService(None)
    summary = svc.get_portfolio_summary({})

    assert "total_return_pct" in summary
    assert summary["total_return_pct"] == 0.0
    assert summary["cash"] == 1000000.0
    assert isinstance(summary["positions_df"], pd.DataFrame)


def test_no_trade_history_summary():
    account = PaperAccount(initial_capital=500000.0)
    account.reset_account(capital=500000.0)
    svc = PortfolioService(account)
    summary = svc.get_portfolio_summary()

    assert summary["initial_capital"] == 500000.0
    assert summary["total_return_pct"] == 0.0
    assert summary["trade_logs_df"].empty


def test_market_data_unavailable():
    account = PaperAccount(initial_capital=1000000.0)
    account.reset_account(capital=1000000.0)
    svc = PortfolioService(account)
    summary = svc.get_portfolio_summary(current_prices=None)

    assert "total_return_pct" in summary
    assert summary["total_equity"] == 1000000.0
    assert summary["market_value"] == 0.0


def test_summary_data_contract_completeness():
    account = PaperAccount(initial_capital=1000000.0)
    account.reset_account(capital=1000000.0)
    svc = PortfolioService(account)
    summary = svc.get_portfolio_summary({"600519": 1500.0})

    required_keys = [
        "initial_capital",
        "cash",
        "market_value",
        "total_equity",
        "equity",
        "total_return_pct",
        "pnl_pct",
        "positions_df",
        "trade_logs_df"
    ]
    for k in required_keys:
        assert k in summary, f"Key '{k}' is missing from PortfolioSummary contract"

