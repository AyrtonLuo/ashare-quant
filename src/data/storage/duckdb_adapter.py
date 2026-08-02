"""
duckdb_adapter.py — Production DuckDB Analytical Query Engine over Parquet partitions.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import duckdb


class DuckDBQueryEngine:
    """DuckDB Analytical Query Engine querying Parquet partitions under data/research/."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "/Users/yuhanluo/ashare-quant/data/research")

    def execute_sql(self, sql_query: str) -> List[Dict[str, Any]]:
        conn = duckdb.connect(database=":memory:")
        try:
            res = conn.execute(sql_query).fetchall()
            cols = [desc[0] for desc in conn.description]
            return [dict(zip(cols, row)) for row in res]
        finally:
            conn.close()

    def query_symbol_ohlcv(self, dataset_id: str, symbol: str) -> List[Dict[str, Any]]:
        sym_clean = symbol.replace(".", "_")
        parquet_file = self.data_dir / dataset_id / f"{sym_clean}.parquet"
        if not parquet_file.exists():
            return []

        query = f"""
            SELECT symbol, trading_date, open_price, high_price, low_price, close_price, volume, amount
            FROM read_parquet('{parquet_file}')
            ORDER BY trading_date ASC
        """
        return self.execute_sql(query)

    def query_dataset_summary(self, dataset_id: str) -> Dict[str, Any]:
        dataset_path = self.data_dir / dataset_id / "*.parquet"
        if not list(self.data_dir.glob(f"{dataset_id}/*.parquet")):
            return {"symbol_count": 0, "total_rows": 0}

        query = f"""
            SELECT COUNT(DISTINCT symbol) as symbol_count, COUNT(*) as total_rows
            FROM read_parquet('{dataset_path}')
        """
        res = self.execute_sql(query)
        return res[0] if res else {"symbol_count": 0, "total_rows": 0}
