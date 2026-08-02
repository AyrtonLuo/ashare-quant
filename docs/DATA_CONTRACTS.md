# 📜 Data Contracts — Canonical Data Schemas

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Canonical Symbol Representation

All securities use standard dot notation:
- `600519.SH` (Shanghai Stock Exchange)
- `000001.SZ` (Shenzhen Stock Exchange)
- `300750.SZ` (ChiNext)
- `688981.SH` (STAR Market)
- `000300.SH` (CSI 300 Index)

---

## 2. Core Contract Definitions (Python Data Classes / Pydantic)

### Contract 1: Market Data Contract (`MarketDataContract`)
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class MarketDataContract:
    symbol: str               # e.g., "600519.SH"
    timestamp: datetime       # ISO 8601 UTC / Local
    trading_date: str         # "YYYY-MM-DD"
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float             # Shares traded
    amount: float             # Currency amount traded
    adj_factor: float         # Corporate action adjustment multiplier
    unadjusted_close: float
    trading_status: str       # "NORMAL", "SUSPENDED", "HALTED"
    quality_status: str       # "VERIFIED", "SUSPECT", "INVALID"
```

### Contract 2: Fundamental Data Contract (`FundamentalDataContract`)
```python
@dataclass(frozen=True)
class FundamentalDataContract:
    symbol: str
    report_date: str          # Period date e.g., "2025-12-31"
    announcement_date: str    # PIT Publish Date e.g., "2026-03-31"
    pe_lyr: Optional[float]   # Price-to-Earnings Last Year Reported
    pe_ttm: Optional[float]   # Price-to-Earnings Trailing Twelve Months
    pb: Optional[float]       # Price-to-Book
    ps: Optional[float]       # Price-to-Sales
    dividend_yield: Optional[float]
    eps: Optional[float]
    roe: Optional[float]
    revenue: Optional[float]
    net_income: Optional[float]
    total_assets: Optional[float]
    total_liabilities: Optional[float]
    operating_cash_flow: Optional[float]
    shares_outstanding: float
    market_cap: float
    quality_status: str
```

### Contract 3: Quality & Lineage Metadata (`DataLineageContract`)
```python
@dataclass(frozen=True)
class DataLineageContract:
    symbol: str
    field_name: str
    provider_name: str
    fetch_timestamp: datetime
    verification_status: str
    cross_check_diff_pct: float
    error_message: Optional[str]
```
