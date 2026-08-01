"""
Tests for the A-share paper trading execution engine.
"""

import pandas as pd

from src.execution import paper_trader


def test_rebalance_uses_chinese_latest_price_column(monkeypatch, tmp_path):
    account_file = tmp_path / "paper_account.json"
    monkeypatch.setattr(paper_trader, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(paper_trader, "PAPER_ACCOUNT_FILE", str(account_file))

    account = paper_trader.PaperAccount(initial_capital=100000.0)
    target = pd.DataFrame(
        [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "target_weight": 0.50,
                "最新价": 100.0,
            }
        ]
    )

    result = account.rebalance(target, market_regime_info={"equity_cap_pct": 100.0})

    assert result["status"] == "success"
    assert account.positions["600519"]["cost_price"] == 100.0
    assert account.positions["600519"]["shares"] == 500
    assert account.cash == 49987.5


def test_empty_summary_does_not_persist_runtime_date(monkeypatch, tmp_path):
    account_file = tmp_path / "paper_account.json"
    monkeypatch.setattr(paper_trader, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(paper_trader, "PAPER_ACCOUNT_FILE", str(account_file))

    account = paper_trader.PaperAccount(initial_capital=100000.0)
    summary = account.get_summary({})

    assert summary["total_equity"] == 100000.0
    assert not account_file.exists()
