"""
test_parquet_storage.py — Unit Tests for Production Parquet Storage Adapter.
"""

from datetime import datetime
import tempfile
from pathlib import Path
from src.data.contracts.market_data import MarketDataContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter


def test_parquet_storage_save_and_load():
    with tempfile.TemporaryDirectory() as tmp_dir:
        adapter = ParquetStorageAdapter(base_dir=tmp_dir)
        now = datetime.now()
        c = MarketDataContract(
            symbol="600519.SH",
            timestamp=now,
            trading_date="2026-08-01",
            open_price=1633.5,
            high_price=1666.5,
            low_price=1617.0,
            close_price=1650.0,
            volume=50000.0,
            amount=8250000050.0,
            adj_factor=1.0,
            unadjusted_close=1650.0,
            trading_status="NORMAL",
            quality_status="VALID"
        )
        adapter.save_market_data("test_ds", [c])

        # Verify Parquet file created on disk
        parquet_file = Path(tmp_dir) / "test_ds" / "600519_SH.parquet"
        assert parquet_file.exists() is True

        loaded = adapter.load_market_data("test_ds", "600519.SH")
        assert len(loaded) == 1
        assert loaded[0].symbol == "600519.SH"
        assert loaded[0].close_price == 1650.0
