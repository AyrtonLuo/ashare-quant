"""
test_duckdb_query.py — Unit Tests for DuckDB Query Engine over Parquet.
"""

from datetime import datetime
import tempfile
from src.data.contracts.market_data import MarketDataContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.storage.duckdb_adapter import DuckDBQueryEngine


def test_duckdb_query_parquet():
    with tempfile.TemporaryDirectory() as tmp_dir:
        parquet_storage = ParquetStorageAdapter(base_dir=tmp_dir)
        duck_engine = DuckDBQueryEngine(data_dir=tmp_dir)
        now = datetime.now()
        
        c = MarketDataContract(
            symbol="000001.SZ",
            timestamp=now,
            trading_date="2026-08-01",
            open_price=11.38,
            high_price=11.61,
            low_price=11.27,
            close_price=11.50,
            volume=1200000.0,
            amount=13800000.0,
            adj_factor=1.0,
            unadjusted_close=11.50,
            trading_status="NORMAL",
            quality_status="VALID"
        )
        parquet_storage.save_market_data("duck_ds", [c])

        res = duck_engine.query_symbol_ohlcv("duck_ds", "000001.SZ")
        assert len(res) == 1
        assert res[0]["symbol"] == "000001.SZ"
        assert res[0]["close_price"] == 11.50
