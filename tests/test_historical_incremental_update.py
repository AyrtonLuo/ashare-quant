"""
test_historical_incremental_update.py — Tests verifying incremental bar appending in Parquet.
"""

from datetime import datetime
import tempfile
from src.data.contracts.market_data import MarketDataContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter


def test_parquet_incremental_update():
    with tempfile.TemporaryDirectory() as tmp_dir:
        adapter = ParquetStorageAdapter(base_dir=tmp_dir)
        now = datetime.now()

        # Day 1
        c1 = MarketDataContract(
            symbol="600519.SH", timestamp=now, trading_date="2026-08-01",
            open_price=1633.5, high_price=1666.5, low_price=1617.0, close_price=1650.0,
            volume=50000.0, amount=82500000.0, adj_factor=1.0, unadjusted_close=1650.0,
            trading_status="NORMAL", quality_status="VALID"
        )
        adapter.save_market_data("inc_ds", [c1])

        # Day 2
        c2 = MarketDataContract(
            symbol="600519.SH", timestamp=now, trading_date="2026-08-02",
            open_price=1650.0, high_price=1670.0, low_price=1640.0, close_price=1660.0,
            volume=48000.0, amount=79680000.0, adj_factor=1.0, unadjusted_close=1660.0,
            trading_status="NORMAL", quality_status="VALID"
        )
        adapter.save_market_data("inc_ds", [c2])

        loaded = adapter.load_market_data("inc_ds", "600519.SH")
        assert len(loaded) == 2
        assert loaded[0].trading_date == "2026-08-01"
        assert loaded[1].trading_date == "2026-08-02"
