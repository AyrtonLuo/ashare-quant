# 🧪 Historical Data Validation Specification — Point-in-Time & Quality Gatekeeping

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Validation Rules & Data Trust Gate

Before historical data is appended to Parquet partitions:
1. **Schema & OHLC Sanity**: $High \ge \max(Open, Close)$, $Low \le \min(Open, Close)$, $Open > 0$, $Close > 0$, $Volume \ge 0$.
2. **Point-in-Time Protection**: $available\_at \le query\_as\_of$. Statements announced after simulation date are strictly blocked (`PITGate`).
3. **Survivorship Bias Protection**: Delisted securities remain in historical universes for trading dates prior to their delisting date (`SecurityMasterRegistry`).
4. **Missing Value Handling**: Missing fields are assigned `MISSING` / `UNAVAILABLE`. Automatic zero-filling is strictly prohibited.
