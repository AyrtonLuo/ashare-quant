"""
test_historical_idempotency.py — Tests verifying duplicate symbol-date ingestion is idempotent.
"""

from datetime import datetime
import tempfile
from src.data.contracts.market_data import MarketDataContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter


def test_ingestion_idempotency():
    with tempfile.TemporaryDirectory() as tmp_dir:
        adapter = ParquetStorageAdapter(base_dir=tmp_dir)
        now = datetime.now()

        c1 = MarketDataContract(
            symbol="600519.SH", timestamp=now, trading_date="2026-08-01",
            open_price=1633.5, high_price=1666.5, low_price=1617.0, close_price=1650.0,
            volume=50000.0, amount=82500000.0, adj_factor=1.0, unadjusted_close=1650.0,
            trading_status="NORMAL", quality_status="VALID"
        )

        # Ingest same day twice
        adapter.save_market_data("idem_ds", [c1])
        adapter.save_market_data("idem_ds", [c1])

        loaded = adapter.load_market_data("idem_ds", "600519.SH")
        assert len(loaded) == 1, "Idempotent ingestion must deduplicate identical symbol-date records!"
