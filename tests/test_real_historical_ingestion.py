"""
test_real_historical_ingestion.py — Tests for Historical Ingestion Engine Pipeline.
"""

import tempfile
from src.data.providers.tushare_provider import TuShareAdapter
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.warehouse.ingestion_engine import HistoricalIngestionEngine


def test_historical_ingestion_pipeline():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ParquetStorageAdapter(base_dir=tmp_dir)
        provider = TuShareAdapter()
        engine = HistoricalIngestionEngine(provider=provider, storage_adapter=storage)

        symbols = ["600519.SH", "000001.SZ", "000858.SZ"]
        manifest = engine.ingest_historical_dataset(
            dataset_id="real_test_v1",
            symbols=symbols,
            start_date="2026-08-01",
            end_date="2026-08-01"
        )

        assert manifest.dataset_id == "real_test_v1"
        assert manifest.row_count == 3
        assert manifest.validation_status == "VERIFIED"
