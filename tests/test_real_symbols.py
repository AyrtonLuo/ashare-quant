"""
test_real_symbols.py — Real Symbols Test Pipeline for 600519.SH, 000001.SZ, 000858.SZ.
"""

from src.data.providers.tushare_provider import TuShareAdapter
from src.data.validation.gate import DataTrustGate


def test_real_symbols_pipeline():
    adapter = TuShareAdapter()
    symbols = ["600519.SH", "000001.SZ", "000858.SZ"]

    for sym in symbols:
        m_contract = adapter.fetch_market_data(sym, "2026-08-01")
        f_contract = adapter.fetch_fundamental_data(sym, "2026-08-01")

        is_m_valid, m_errs = DataTrustGate.validate_market_data(m_contract)
        is_f_valid, f_errs = DataTrustGate.validate_fundamental_data(f_contract)

        assert is_m_valid is True, f"Market data invalid for {sym}: {m_errs}"
        assert is_f_valid is True, f"Fundamental data invalid for {sym}: {f_errs}"
