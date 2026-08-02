# 🔄 Backtest Engine Specification — Simulation & Transaction Cost Model

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Simulation Mechanics & Transaction Costs

- **Point-in-Time Gating**: Daily backtest queries query `HistoricalDataWarehouse` strictly using `available_at <= T-1`.
- **A-Share Transaction Cost Model**:
  - Commission: $0.025\%$
  - Sell Stamp Duty: $0.05\%$
  - Slippage: $0.01\%$
