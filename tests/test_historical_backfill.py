"""
test_historical_backfill.py — Tests verifying backfilling multi-year historical ranges.
"""

import tempfile
from src.data.providers.tushare_provider import TuShareAdapter
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.warehouse.ingestion_engine import HistoricalIngestionEngine


def test_historical_backfill_ranges():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ParquetStorageAdapter(base_dir=tmp_dir)
        provider = TuShareAdapter()
        engine = HistoricalIngestionEngine(provider=provider, storage_adapter=storage)

        # Backfill Era 2020-2026
        m_2020 = engine.ingest_historical_dataset("bf_2020", ["600519.SH"], "2020-01-01", "2020-12-31")
        m_2026 = engine.ingest_historical_dataset("bf_2026", ["600519.SH"], "2026-01-01", "2026-08-01")

        assert m_2020.start_date == "2020-01-01"
        assert m_2026.start_date == "2026-01-01"
