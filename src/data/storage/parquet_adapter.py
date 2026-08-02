"""
parquet_adapter.py — Production Apache Parquet Storage Adapter using PyArrow/Pandas.
"""

import os
from pathlib import Path
from typing import List, Optional
import pandas as pd
from src.data.contracts.market_data import MarketDataContract
from src.data.storage.storage_adapter import BaseStorageAdapter


class ParquetStorageAdapter(BaseStorageAdapter):
    """Production Parquet Storage Adapter providing columnar partition storage under data/research/."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "/Users/yuhanluo/ashare-quant/data/research")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_market_data(self, dataset_id: str, contracts: List[MarketDataContract]):
        if not contracts:
            return

        dataset_dir = self.base_dir / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)

        records = [
            {
                "symbol": c.symbol,
                "trading_date": c.trading_date,
                "open_price": c.open_price,
                "high_price": c.high_price,
                "low_price": c.low_price,
                "close_price": c.close_price,
                "volume": c.volume,
                "amount": c.amount,
                "adj_factor": c.adj_factor,
                "unadjusted_close": c.unadjusted_close,
                "trading_status": c.trading_status,
                "quality_status": c.quality_status,
                "available_at": c.timestamp.isoformat()
            }
            for c in contracts
        ]

        df = pd.DataFrame(records)
        # Partition by symbol
        for symbol, group in df.groupby("symbol"):
            sym_clean = symbol.replace(".", "_")
            file_path = dataset_dir / f"{sym_clean}.parquet"
            
            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                combined = pd.concat([existing_df, group]).drop_duplicates(
                    subset=["symbol", "trading_date"], keep="last"
                )
                combined.to_parquet(file_path, index=False, engine="pyarrow")
            else:
                group.to_parquet(file_path, index=False, engine="pyarrow")

    def load_market_data(self, dataset_id: str, symbol: str) -> List[MarketDataContract]:
        sym_clean = symbol.replace(".", "_")
        file_path = self.base_dir / dataset_id / f"{sym_clean}.parquet"

        if not file_path.exists():
            return []

        df = pd.read_parquet(file_path)
        contracts = []
        for _, row in df.iterrows():
            c = MarketDataContract(
                symbol=row["symbol"],
                timestamp=pd.to_datetime(row["available_at"]).to_pydatetime(),
                trading_date=row["trading_date"],
                open_price=float(row["open_price"]),
                high_price=float(row["high_price"]),
                low_price=float(row["low_price"]),
                close_price=float(row["close_price"]),
                volume=float(row["volume"]),
                amount=float(row["amount"]),
                adj_factor=float(row["adj_factor"]),
                unadjusted_close=float(row["unadjusted_close"]),
                trading_status=row["trading_status"],
                quality_status=row["quality_status"]
            )
            contracts.append(c)
        return contracts
