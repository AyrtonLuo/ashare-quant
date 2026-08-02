"""
test_historical_corporate_actions.py — Corporate Action Adjustment Factor Tests.
"""

from src.data.contracts.corporate_action import CorporateActionContract


def test_corporate_action_split_ratio():
    ca = CorporateActionContract(
        symbol="000002.SZ",
        ex_date="2020-06-15",
        action_type="SPLIT",
        cash_amount_per_share=0.0,
        bonus_ratio=1.0,  # 1-to-1 bonus share split
        split_ratio=2.0,
        announcement_date="2020-05-20",
        quality_status="VALID"
    )
    assert ca.split_ratio == 2.0
    assert ca.action_type == "SPLIT"
