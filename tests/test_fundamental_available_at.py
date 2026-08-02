"""
test_fundamental_available_at.py — Fundamental Data Announcement Available_At Tests.
"""

from datetime import datetime
from src.data.contracts.fundamental_data import FundamentalDataContract


def test_fundamental_data_contract_pit_dates():
    fund = FundamentalDataContract(
        symbol="600519.SH",
        trade_date="2026-08-01",
        report_date="2025-12-31",
        announcement_date="2026-03-31",
        currency="CNY",
        revenue=140000000000.0,
        net_income=74000000000.0,
        eps_annual=58.0,
        eps_ttm=58.0,
        book_value_per_share=180.0,
        operating_cash_flow=80000000000.0,
        shares_outstanding=1256000000.0,
        market_cap=2072400000000.0,
        pe_lyr=28.4483,
        pe_ttm=28.4483,
        pe_ttm_status="VALID",
        pb=9.1667,
        pb_status="VALID",
        dividend_yield_ttm=1.5152,
        dividend_yield_status="VALID",
        roe=32.2,
        quality_status="VALID"
    )
    assert fund.report_date < fund.announcement_date
    assert fund.announcement_date == "2026-03-31"
