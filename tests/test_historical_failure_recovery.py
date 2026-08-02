"""
test_historical_failure_recovery.py — Tests verifying failure recovery during ingestion.
"""

import tempfile
from src.data.providers.tushare_provider import TuShareAdapter
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.warehouse.ingestion_engine import HistoricalIngestionEngine


def test_failure_recovery_skips_invalid_symbols_safely():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ParquetStorageAdapter(base_dir=tmp_dir)
        provider = TuShareAdapter()
        engine = HistoricalIngestionEngine(provider=provider, storage_adapter=storage)

        # Mix valid and invalid symbol
        symbols = ["600519.SH", "INVALID_BAD_SYMBOL"]
        manifest = engine.ingest_historical_dataset("fail_rec_ds", symbols, "2026-08-01", "2026-08-01")

        # Invalid symbol failed safely without crashing; valid symbol succeeded
        assert manifest.row_count == 1
        assert manifest.validation_status == "VERIFIED"
