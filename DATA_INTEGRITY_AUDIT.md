# 🛡️ DATA INTEGRITY & MARKET DATA PROVENANCE AUDIT REPORT

**Audit Date**: 2026-08-01  
**Refactor Phase**: Phase 15 - Real Market Data Integrity Refactor  
**Mandate**: **RESEARCH MODE must NEVER display Hardcoded, Mock, Demo, or Static fake prices. When real data is unavailable, it MUST return `DATA_UNAVAILABLE` / `N/A`.**

---

## 1. Executive Summary & Policy Enforcements

1. **Zero Hardcoded Prices in Research Mode**: 所有在 `AkShareProvider`, `realtime_engine.py`, `app.py` 中遗留的静态价格 (如 `3280.50`, `3832.26`, `11.50`, `10.00`) 均已彻底清理移除；
2. **Symbol Namespace Isolation**: 强行隔离 `000001.SH` (上证指数) 与 `000001.SZ` (平安银行)，Parquet 缓存按 `data/indices/` 与 `data/stocks/` 分别独立归档，拒绝任何模糊裸代码猜测；
3. **Data Lineage Metadata Guarantee**: 每一个 `MarketData` 对象强校验 `symbol`, `close`, `timestamp`, `source`, `data_mode`, `is_real`, `status`；
4. **Strict Isolation**: `RESEARCH MODE` 绝不退化至 `DemoMarketDataProvider` 或假价格。API 全不可用时一律返回 `status="DATA_UNAVAILABLE"`, `close=None`；
5. **Research Integrity Gate (`src/system/integrity_gate.py`)**: 任何试图将 `DATA_UNAVAILABLE` 或 `is_real=False` 数据推入量化计算引擎的操作均被直接中断并抛出 `ResearchDataIntegrityError`。

---

## 2. Real Market Data Lineage Matrix

| Symbol / Target | Internal Namespace | Exchange | Provider / Source | Fallback Chain | Data Mode | Is Real | Failure Status | Validation Status |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **上证指数** | `000001.SH` | SH | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **深证成指** | `399001.SZ` | SZ | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **创业板指** | `399006.SZ` | SZ | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **沪深300** | `000300.SH` | SH | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **中证1000** | `000852.SH` | SH | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **平安银行** | `000001.SZ` | SZ | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **贵州茅台** | `600519.SH` | SH | AkShare / Tencent | AkShare $\rightarrow$ Tencent $\rightarrow$ `DATA_UNAVAILABLE` | RESEARCH | **True** | `N/A / None` | **VERIFIED** |
| **Demo 标的** | `000001.SH` | SH | DemoProvider | Pure Static Demo Dataset | DEMO | **False** | `AVAILABLE (Demo)` | **ISOLATED** |
