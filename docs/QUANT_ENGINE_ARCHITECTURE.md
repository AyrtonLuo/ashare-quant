# 🧮 Quant Engine Architecture — Unidirectional Flow & Isolation Layer

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Unidirectional Execution Pipeline

The Quant Engine Core enforces strict unidirectional data flow without circular dependencies:

```text
HistoricalDataWarehouse (Parquet / DuckDB)
          │
          ▼
   ResearchDataAPI (src/quant/data/research_api.py)
          │
          ▼
   Factor Engine (src/quant/factors/)
          │
          ▼
   Signal Engine (src/quant/signals/engine.py)
          │
          ▼
 Strategy Definition (src/quant/strategies/)
          │
          ▼
 Portfolio Construction (src/quant/portfolio/construction.py)
          │
          ▼
 Backtest Engine (src/quant/backtest/engine.py)
          │
          ▼
 Performance Analytics (src/quant/performance/analytics.py)
          │
          ▼
 ResearchRunManifest (src/quant/reproducibility/manifest.py)
```

---

## 2. Hard Boundaries & Zero Leakage

- **Zero Broker / Live Execution**: 100% pure backtesting, paper portfolio simulation, and quant factor research. Zero live order APIs.
- **Zero Direct Provider Imports**: `src/quant/` modules import **ONLY** `Canonical Data Contracts` & `HistoricalDataWarehouse`. Zero direct imports of `tushare` or `akshare`.
- **Deterministic Math Engine**: LLMs/AI do NOT compute financial ratios, Sharpe, returns, or drawdowns. All quantitative metrics are computed by deterministic Python algorithms.
