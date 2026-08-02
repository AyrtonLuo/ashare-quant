"""
test_golden_dataset.py — Golden Dataset Validation Tests for Representative A-Share Cases.
"""

import json
from pathlib import Path
from src.data.fundamentals.metrics.calculator import FinancialMetricsCalculator


def test_golden_dataset_validation():
    golden_file = Path(__file__).parent / "data" / "golden" / "golden_stocks.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        symbol = case["symbol"]
        price = case["test_price"]
        eps = case["annual_eps"]
        bvps = case["book_value_per_share"]
        div = case["cash_dividend_12m"]

        pe, pe_status = FinancialMetricsCalculator.calculate_pe_lyr(price, eps)
        pb, pb_status = FinancialMetricsCalculator.calculate_pb(price, bvps)
        dy, dy_status = FinancialMetricsCalculator.calculate_dividend_yield_ttm(price, div)

        assert pe == case["expected_pe_lyr"], f"Failed PE for {symbol}"
        assert pe_status == case["expected_pe_lyr_status"], f"Failed PE Status for {symbol}"
        assert pb == case["expected_pb"], f"Failed PB for {symbol}"
        assert pb_status == case["expected_pb_status"], f"Failed PB Status for {symbol}"
        assert dy == case["expected_dividend_yield_ttm"], f"Failed Dividend Yield for {symbol}"
        assert dy_status == case["expected_dividend_yield_status"], f"Failed Dividend Yield Status for {symbol}"
