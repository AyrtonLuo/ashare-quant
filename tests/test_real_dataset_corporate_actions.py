"""
test_real_dataset_corporate_actions.py — Corporate actions consistency tests on real datasets.
"""

import pytest
from src.data.providers.tushare_provider import TuShareAdapter


def test_real_dataset_corporate_action_fetching():
    adapter = TuShareAdapter()
    actions = adapter.fetch_corporate_actions("600519.SH", "2026-01-01", "2026-12-31")

    assert len(actions) == 1
    assert actions[0].symbol == "600519.SH"
    assert actions[0].action_type == "CASH_DIVIDEND"
    assert actions[0].cash_amount_per_share == 25.0
